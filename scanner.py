# -*- coding: utf-8 -*-
"""
СКАНЕР ВСЕХ РЫНКОВ — бот смотрит на все классы активов и даёт сигнал по каждому.
Металлы, энергия, облигации, акции, индексы, крипта, форекс.
Данные: yfinance (бесплатно). Сигнал: наша проверенная стратегия «тренд».
Запуск: python scanner.py
"""
import pandas as pd
import yfinance as yf

import strategies

SCAN_STRATEGY = "trend"  # какой стратегией оцениваем (проверенная лучшая)

UNIVERSE = {
    "🥇 Драгоценные и редкие металлы": {
        "Золото": "GC=F", "Серебро": "SI=F", "Платина": "PL=F",
        "Палладий": "PA=F", "Медь": "HG=F"},
    "🛢️ Энергия": {"Нефть Brent": "BZ=F", "Нефть WTI": "CL=F", "Газ": "NG=F"},
    "📜 Облигации": {"Гособлигации США 20y (TLT)": "TLT", "10y (IEF)": "IEF"},
    "🏢 Акции": {"Apple": "AAPL", "Microsoft": "MSFT", "Nvidia": "NVDA", "Tesla": "TSLA"},
    "📊 Индексы": {"S&P 500 (SPY)": "SPY", "Nasdaq (QQQ)": "QQQ"},
    "₿ Крипта": {"Bitcoin": "BTC-USD", "Ethereum": "ETH-USD"},
    "💱 Форекс": {"EUR/USD": "EURUSD=X", "USD/JPY": "JPY=X"},
}

tickers = [t for grp in UNIVERSE.values() for t in grp.values()]
print(f"Скачиваю данные по {len(tickers)} инструментам...")
raw = yf.download(tickers, start="2023-01-01", progress=False, auto_adjust=True, group_by="ticker")


def ohlc(tk):
    d = raw[tk].dropna().reset_index()
    d.columns = [str(c).lower() for c in d.columns]
    d = d.rename(columns={"date": "dt"})
    return d[["dt", "open", "high", "low", "close"]]


print("\n" + "=" * 68)
print(f"  📡 СКАНЕР РЫНКОВ · сигнал по стратегии «{SCAN_STRATEGY}»")
print("=" * 68)
bulls, bears = [], []
for group, items in UNIVERSE.items():
    print(f"\n{group}")
    for name, tk in items.items():
        try:
            df = ohlc(tk)
            if len(df) < 210:
                print(f"  {name:28} — мало данных"); continue
            pos, txt, row = strategies.signal_now(SCAN_STRATEGY, df)
            price = row["close"]
            chg = (df["close"].iloc[-1] / df["close"].iloc[-22] - 1) * 100  # ~месяц
            print(f"  {name:28} {txt:20} цена {price:>10.2f}  ({chg:+.1f}%/мес)")
            (bulls if pos == 1 else bears).append(name)
        except Exception as e:
            print(f"  {name:28} — ошибка ({type(e).__name__})")
print("\n" + "=" * 68)
print(f"  🟢 В ЛОНГЕ по тренду ({len(bulls)}): {', '.join(bulls) if bulls else '—'}")
print(f"  ⚪ ВНЕ РЫНКА ({len(bears)}): {', '.join(bears) if bears else '—'}")
print("=" * 68)
print("  Это АНАЛИЗ по всем рынкам. Торговать вживую на демо бот может")
print("  крипту и золото (Binance). Акции — через Alpaca (бесплатно). ")
