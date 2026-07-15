# -*- coding: utf-8 -*-
"""
СВЕЧНОЙ бот — читает японские свечи + индикаторы, решает БЫК / МЕДВЕДЬ.
То, что просил Усон: паттерны свечей + «формула» (RSI, MACD, тренд) → направление.
Сразу честная проверка на золоте 2008-2026 (лонг/шорт и лонг/кэш) vs «купи и держи».
Запуск: python candle_bot.py
"""
import numpy as np
import pandas as pd
import yfinance as yf
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator

# ── данные: золото OHLC ──
d = yf.download("GC=F", start="2008-01-01", progress=False, auto_adjust=True)
if isinstance(d.columns, pd.MultiIndex):
    d.columns = d.columns.get_level_values(0)
df = d[["Open", "High", "Low", "Close"]].dropna().reset_index()
df.columns = ["dt", "open", "high", "low", "close"]
df["year"] = df["dt"].dt.year

# ── СВЕЧНЫЕ ПАТТЕРНЫ (ручное распознавание) ──
body = (df.close - df.open).abs()
upsh = df.high - df[["open", "close"]].max(axis=1)
losh = df[["open", "close"]].min(axis=1) - df.low
green = df.close > df.open
red = df.close < df.open
p_open, p_close = df.open.shift(1), df.close.shift(1)

hammer = (losh > 2 * body) & (upsh < body) & (body > 0)                 # молот — бык
star = (upsh > 2 * body) & (losh < body) & (body > 0)                   # звезда — медведь
bull_engulf = red.shift(1) & green & (df.open < p_close) & (df.close > p_open)   # бычье поглощение
bear_engulf = green.shift(1) & red & (df.open > p_close) & (df.close < p_open)   # медвежье поглощение

# ── ИНДИКАТОРЫ («формула») ──
rsi = RSIIndicator(df.close, window=14).rsi()
macd_diff = MACD(df.close).macd_diff()
sma50 = SMAIndicator(df.close, window=50).sma_indicator()

# ── СЧЁТ: складываем сигналы за быка (+) и медведя (−) ──
score = pd.Series(0, index=df.index, dtype=float)
score += hammer.astype(int) + bull_engulf.astype(int)         # свечи-быки
score -= star.astype(int) + bear_engulf.astype(int)           # свечи-медведи
score += (rsi < 30).astype(int) - (rsi > 70).astype(int)      # RSI
score += (macd_diff > 0).astype(int) - (macd_diff < 0).astype(int)  # MACD
score += (df.close > sma50).astype(int) - (df.close < sma50).astype(int)  # тренд

signals = {
    "Купи и держи": pd.Series(1.0, index=df.index),
    "Свечи: ЛОНГ/ШОРТ": pd.Series(np.select([score >= 2, score <= -2], [1, -1], 0), index=df.index),
    "Свечи: ЛОНГ/кэш": (score >= 2).astype(float),
}


def bt(pos, fee=0.0005, ppy=252, mask=None):
    p = pos.shift(1).fillna(0)
    ret = df.close.pct_change().fillna(0)
    if mask is not None:
        p, ret = p[mask], ret[mask]
    strat = p * ret - p.diff().abs().fillna(0) * fee
    eq = (1 + strat).cumprod()
    yrs = max(len(ret) / ppy, 0.1)
    return dict(total=eq.iloc[-1] - 1, cagr=eq.iloc[-1] ** (1 / yrs) - 1,
                dd=float((eq / eq.cummax() - 1).min()),
                sharpe=float(strat.mean() / strat.std() * np.sqrt(ppy)) if strat.std() else 0,
                eq=eq)


print("=" * 84)
print(f"  СВЕЧНОЙ БОТ на золоте {df.dt.iloc[0].date()}–{df.dt.iloc[-1].date()} ({len(df)} дней)")
print("=" * 84)
print(f"{'Стратегия':22} {'Доход':>10} {'CAGR':>8} {'Просадка':>9} {'Sharpe':>7}")
print("-" * 84)
res = {}
for name, pos in signals.items():
    m = bt(pos); res[name] = m
    print(f"{name:22} {m['total']*100:+9.0f}% {m['cagr']*100:+7.1f}% {m['dd']*100:8.1f}% {m['sharpe']:7.2f}")
print("-" * 84)

# доходность по годам для свечного лонг/шорт (стабильно или казино?)
print("\nСвечной ЛОНГ/ШОРТ по годам (стабильность):")
ls = signals["Свечи: ЛОНГ/ШОРТ"]
years = sorted(df.year.unique())
line = ""
wins = 0
for y in years:
    r = bt(ls, mask=(df.year == y))["total"]
    wins += r > 0
    line += f"{y}:{r*100:+.0f}%  "
    if len(line) > 70:
        print("  " + line); line = ""
if line:
    print("  " + line)
print(f"\n  Прибыльных лет: {wins} из {len(years)}")

# вердикт
bh, ls_m, lf_m = res["Купи и держи"], res["Свечи: ЛОНГ/ШОРТ"], res["Свечи: ЛОНГ/кэш"]
print("\nВЕРДИКТ:")
best = max([("ЛОНГ/ШОРТ", ls_m), ("ЛОНГ/кэш", lf_m)], key=lambda x: x[1]["sharpe"])
if best[1]["cagr"] > bh["cagr"]:
    print(f"  ✅ Свечной бот «{best[0]}» обыграл купи-держи по доходности!")
else:
    print(f"  ⚠️  Свечной бот не обыграл купи-держи по доходу (buy&hold CAGR {bh['cagr']*100:+.1f}%).")
if ls_m["total"] < 0:
    print(f"  ❌ Лонг/шорт версия ушла в МИНУС ({ls_m['total']*100:+.0f}%) — шорт по свечам не работает.")
