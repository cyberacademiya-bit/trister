# -*- coding: utf-8 -*-
"""
МОЗГ бота «Тристер» — логика решений по золоту.

Что мы проверили (2008-2026, с антизаглядыванием):
  • Простой ТРЕНД-фильтр (MA50>MA200 + цена>MA200) — лучший по риск/доходности
    (Sharpe 0.56, прошёл крах 2013 с −5% против −28% у «купи и держи»).
  • COT из книги Уильямса — НЕ улучшил результат на золоте: добавляя его, теряем
    и доход, и Sharpe. Поэтому COT по умолчанию ВЫКЛЮЧЕН (оставлен опцией).

ПРАВИЛО ЛОНГА (держим золото), всё должно совпасть:
  1) MA50 > MA200   — восходящий тренд
  2) цена > MA200   — выше долгосрочной средней (защита от «падающего ножа»)
  3) [опционально]  COT-индекс ≥ floor — если включить use_cot=True
Иначе → кэш (USDT). Шорт не используем: в бэктесте проигрывал.

`python brain.py` — самопроверка на длинной истории.
"""
import numpy as np
import pandas as pd

USE_COT = False   # данные показали: COT ухудшает risk-adjusted → по умолчанию выкл.
COT_FLOOR = 25    # если включить COT: вето только при глубоком шорте коммерсантов


def add_indicators(df):
    df = df.copy()
    df["ma50"] = df["close"].rolling(50).mean()
    df["ma200"] = df["close"].rolling(200).mean()
    return df


def position_series(df, use_cot=USE_COT, cot_floor=COT_FLOOR, cot_col="comm_idx"):
    """Позиция мозга (0/1) для бэктеста. df: close, ma50, ma200 [, cot_col]."""
    sig = (df["ma50"] > df["ma200"]) & (df["close"] > df["ma200"])
    if use_cot and cot_col in df.columns:
        sig = sig & (df[cot_col] >= cot_floor)
    return sig.astype(int)


def live_signal(price_df, cot_index=None, use_cot=USE_COT, cot_floor=COT_FLOOR):
    """Живое решение бота. price_df: дневные свечи (dt, close); cot_index: текущий COT %."""
    d = add_indicators(price_df.sort_values("dt"))
    price = float(d["close"].iloc[-1])
    ma50 = float(d["ma50"].iloc[-1])
    ma200 = float(d["ma200"].iloc[-1])
    trend_up = ma50 > ma200
    above_long = price > ma200
    cot_ok = (cot_index is None) or (cot_index >= cot_floor)
    go_long = trend_up and above_long and (cot_ok if use_cot else True)
    return go_long, dict(price=price, ma50=ma50, ma200=ma200,
                         trend_up=trend_up, above_long=above_long,
                         cot_index=cot_index, cot_ok=cot_ok, use_cot=use_cot)


# ─────────────── САМОПРОВЕРКА ───────────────
def _bt(df, pos, fee=0.0005, ppy=252, mask=None):
    p = pos.shift(1).fillna(0)
    ret = df["close"].pct_change().fillna(0)
    if mask is not None:
        p, ret = p[mask], ret[mask]
    strat = p * ret - p.diff().abs().fillna(0) * fee
    eq = (1 + strat).cumprod()
    yrs = max(len(ret) / ppy, 0.1)
    return dict(cagr=eq.iloc[-1] ** (1 / yrs) - 1, dd=float((eq / eq.cummax() - 1).min()),
                sharpe=float(strat.mean() / strat.std() * np.sqrt(ppy)) if strat.std() else 0)


if __name__ == "__main__":
    df = add_indicators(pd.read_csv("Данные/gold_cot_merged.csv", parse_dates=["dt"]).sort_values("dt").reset_index(drop=True))
    m2013 = df["dt"].dt.year == 2013
    print("Проверка мозга (золото 2008-2026):")
    print(f"{'Вариант':34} {'CAGR':>7} {'Просадка':>9} {'Sharpe':>7} {'2013':>8}")
    print("-" * 70)
    for name, pos in {
        "Купи и держи": pd.Series(1, index=df.index).astype(float),
        "МОЗГ: тренд (по умолчанию) ★": position_series(df),
        "МОЗГ: тренд + COT (опция)": position_series(df, use_cot=True),
    }.items():
        m = _bt(df, pos); r13 = _bt(df, pos, mask=m2013)
        print(f"{name:34} {m['cagr']*100:+6.1f}% {m['dd']*100:8.1f}% {m['sharpe']:7.2f} {r13['cagr']*100:+7.1f}%")
