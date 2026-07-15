# -*- coding: utf-8 -*-
"""
4H МНОГОТАЙМФРЕЙМОВЫЙ бот — лонг/шорт по «формулам из книг» (EMA-тренд + MACD + RSI).
Проверка: работает или нет, на 4h свечах BTC/ETH/золото. Как всегда — честный бэктест.
Запуск: python mtf_bot.py
"""
import numpy as np
import pandas as pd
from ta.trend import EMAIndicator, MACD
from ta.momentum import RSIIndicator

import data

SYMBOLS = {"Bitcoin": "BTC/USDT", "Ethereum": "ETH/USDT", "Золото": "PAXG/USDT"}
FEE, PPY = 0.0005, 6 * 365   # 4h: 6 свечей в сутки


def strat(df):
    c = df["close"]
    ema_f = EMAIndicator(c, 20).ema_indicator()
    ema_s = EMAIndicator(c, 50).ema_indicator()
    macd = MACD(c).macd_diff()
    rsi = RSIIndicator(c, 14).rsi()
    long = (ema_f > ema_s) & (macd > 0) & (rsi < 75)
    short = (ema_f < ema_s) & (macd < 0) & (rsi > 25)
    return pd.Series(np.select([long, short], [1.0, -1.0], 0.0), index=df.index)


def bt(df, pos):
    p = pos.shift(1).fillna(0)
    ret = df["close"].pct_change().fillna(0)
    strat_ret = p * ret - p.diff().abs().fillna(0) * FEE
    eq = (1 + strat_ret).cumprod()
    yrs = max(len(ret) / PPY, 0.1)
    trades = int((p.diff().abs() > 0).sum())
    return dict(total=eq.iloc[-1] - 1, cagr=eq.iloc[-1] ** (1 / yrs) - 1,
                dd=float((eq / eq.cummax() - 1).min()),
                sharpe=float(strat_ret.mean() / strat_ret.std() * np.sqrt(PPY)) if strat_ret.std() else 0,
                trades=trades)


print("Тяну 4h свечи (BTC/ETH/золото, ~1.5 года)...")
print("=" * 74)
print(f"{'Рынок':10} {'Стратегия':18} {'Доход':>9} {'CAGR':>8} {'Просадка':>9} {'Sharpe':>7} {'сделок':>7}")
print("-" * 74)
agg = {"4h лонг/шорт": [], "buyhold": []}
for name, sym in SYMBOLS.items():
    df = data.fetch_ohlcv(symbol=sym, timeframe="4h", days=550, use_cache=False)
    ls = bt(df, strat(df))
    bh = bt(df, pd.Series(1.0, index=df.index))
    agg["4h лонг/шорт"].append(ls["cagr"]); agg["buyhold"].append(bh["cagr"])
    print(f"{name:10} {'4h лонг/шорт':18} {ls['total']*100:+8.0f}% {ls['cagr']*100:+7.1f}% {ls['dd']*100:8.1f}% {ls['sharpe']:7.2f} {ls['trades']:7d}")
    print(f"{'':10} {'купи и держи':18} {bh['total']*100:+8.0f}% {bh['cagr']*100:+7.1f}% {bh['dd']*100:8.1f}% {bh['sharpe']:7.2f} {0:7d}")
    print("-" * 74)

m_ls = np.mean(agg["4h лонг/шорт"]) * 100
m_bh = np.mean(agg["buyhold"]) * 100
print(f"\nСРЕДНЕЕ CAGR: 4h лонг/шорт {m_ls:+.1f}%  vs  купи-держи {m_bh:+.1f}%")
print("✅ обыграл" if m_ls > m_bh else "❌ проиграл купи-держи (как и другие 'умные' стратегии)")
