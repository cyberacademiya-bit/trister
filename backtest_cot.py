# -*- coding: utf-8 -*-
"""
COT-бэктест: проверяем, даёт ли индекс Уильямса (позиции коммерсантов) преимущество
на золоте против «купи и держи». Запуск: python backtest_cot.py

Логика: COT выходит еженедельно (вторник), публикуется в пятницу. Чтобы не заглядывать
в будущее, сигнал становится доступен через +4 дня и применяется на СЛЕДУЮЩИЙ день.
"""
import numpy as np
import pandas as pd

import data

FEE = 0.001          # 0.1% за сделку
PPY = 365            # дней в году (дневной таймфрейм)
INITIAL = 1000.0


def metrics(df, pos):
    r = df["close"].pct_change().fillna(0)
    strat = df[pos] * r
    trades_mask = df[pos].diff().abs().fillna(0)
    strat = strat - trades_mask * FEE
    eq = INITIAL * (1 + strat).cumprod()
    total = eq.iloc[-1] / INITIAL - 1
    dd = float((eq / eq.cummax() - 1).min())
    sharpe = float(strat.mean() / strat.std() * np.sqrt(PPY)) if strat.std() > 0 else 0.0
    entries = int((df[pos].diff() == 1).sum())
    # доля времени в рынке
    in_market = float((df[pos] > 0).mean())
    return dict(total=total, dd=dd, sharpe=sharpe, entries=entries, inmkt=in_market)


def main():
    print("Загружаю дневные свечи золота (PAXG/USDT)...")
    px = data.fetch_ohlcv(symbol="PAXG/USDT", timeframe="1d", days=1000, use_cache=False)
    px = px[["dt", "close"]].sort_values("dt").reset_index(drop=True)
    px["dt"] = px["dt"].astype("datetime64[ns]")

    cot = pd.read_csv("Данные/gold_williams_cot_index.csv", parse_dates=["date"])
    cot["date"] = cot["date"].astype("datetime64[ns]")
    cot = cot.dropna(subset=["williams_cot_index"]).sort_values("date")
    # антизаглядывание: отчёт (вторник) доступен только с пятницы (+4 дня)
    cot["available"] = cot["date"] + pd.Timedelta(days=4)

    df = pd.merge_asof(px, cot[["available", "williams_cot_index"]].sort_values("available"),
                       left_on="dt", right_on="available", direction="backward")
    df = df.dropna(subset=["williams_cot_index"]).reset_index(drop=True)
    df["ma50"] = df["close"].rolling(50).mean()

    print(f"Период: {df['dt'].iloc[0].date()} → {df['dt'].iloc[-1].date()} | дней: {len(df)}")
    print(f"Индекс COT: от {df['williams_cot_index'].min():.0f}% до {df['williams_cot_index'].max():.0f}%\n")

    # ── варианты стратегий (position на следующий день, без заглядывания) ──
    df["buyhold"] = 1
    df["cot50"] = (df["williams_cot_index"] > 50).astype(int).shift(1).fillna(0)
    df["cot75"] = (df["williams_cot_index"] > 75).astype(int).shift(1).fillna(0)
    df["cot_trend"] = ((df["williams_cot_index"] > 50) & (df["close"] > df["ma50"])).astype(int).shift(1).fillna(0)

    variants = [
        ("Купи и держи (эталон)", "buyhold"),
        ("COT > 50 (умеренно)", "cot50"),
        ("COT > 75 (строго)", "cot75"),
        ("COT > 50 + тренд (цена>MA50)", "cot_trend"),
    ]

    print(f"{'Стратегия':32} {'Доход':>9} {'Просадка':>9} {'Sharpe':>7} {'Сделок':>7} {'В рынке':>8}")
    print("-" * 78)
    bh = None
    rows = []
    for name, col in variants:
        m = metrics(df, col)
        if col == "buyhold":
            bh = m["total"]
        print(f"{name:32} {m['total']*100:+8.1f}% {m['dd']*100:8.1f}% {m['sharpe']:7.2f} {m['entries']:7d} {m['inmkt']*100:7.0f}%")
        rows.append((name, col, m))
    print("-" * 78)

    # честный вердикт
    print("\nВЕРДИКТ:")
    best = max((r for r in rows if r[1] != "buyhold"), key=lambda r: r[2]["total"])
    beat = best[2]["total"] - bh
    if beat > 0:
        print(f"  ✅ Лучшая COT-стратегия «{best[0]}» ОБЫГРАЛА купи-держи на {beat*100:+.1f}%.")
    else:
        print(f"  ⚠️  Ни одна COT-стратегия не обыграла купи-держи (лучшая — «{best[0]}», отстаёт на {beat*100:.1f}%).")
        print("     Это ожидаемо: золото в сильном бычьем тренде, любой выход из рынка проигрывает удержанию.")
    # смотрим на просадку — COT часто её снижает
    bh_dd = next(r[2]["dd"] for r in rows if r[1] == "buyhold")
    if best[2]["dd"] > bh_dd:
        print(f"  💡 Но просадка у «{best[0]}» мягче: {best[2]['dd']*100:.1f}% против {bh_dd*100:.1f}% у купи-держи.")


if __name__ == "__main__":
    main()
