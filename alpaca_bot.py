# -*- coding: utf-8 -*-
"""
Бот для АКЦИЙ через Alpaca (бесплатный paper-trading демо, аналог Binance-демо).
Ключи в .env:  ALPACA_KEY=...  ALPACA_SECRET=...

  python alpaca_bot.py --compare   → сигналы по акциям (работает и без ключей)
  python alpaca_bot.py             → торговать на paper-счёте
"""
import os
import sys

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

import config
import strategies

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
KEY = os.getenv("ALPACA_KEY")
SECRET = os.getenv("ALPACA_SECRET")
STRAT = config.STRATEGY


def get_signals():
    tickers = config.STOCK_UNIVERSE
    raw = yf.download(tickers, start="2023-01-01", progress=False, auto_adjust=True, group_by="ticker")
    out = {}
    for tk in tickers:
        try:
            d = raw[tk].dropna().reset_index()
            d.columns = [str(c).lower() for c in d.columns]
            d = d.rename(columns={"date": "dt"})
            df = d[["dt", "open", "high", "low", "close"]]
            pos, txt, _ = strategies.signal_now(STRAT, df)
            out[tk] = (pos, txt, float(df["close"].iloc[-1]))
        except Exception:
            out[tk] = (None, "нет данных", None)
    return out


SETUP = """
⚠️  Нет ключей Alpaca. Как получить (бесплатно, 3 минуты):
  1. Зайди на https://alpaca.markets  →  Sign Up
  2. В кабинете переключись на «Paper Trading» (демо-режим, вверху)
  3. Слева «API Keys»  →  Generate New Key
  4. Скопируй API Key ID и Secret Key
  5. Кинь их мне — я впишу в .env, и бот начнёт торговать акции на демо.
"""


def main():
    sig = get_signals()

    if not KEY or not SECRET:
        print(SETUP)
        print("Пока без ключей — вот СИГНАЛЫ по акциям (анализ уже работает):")
        print("-" * 50)
        for tk, (pos, txt, price) in sig.items():
            p = f"{price:.2f}" if price else "—"
            print(f"  {tk:6} {txt:20} {p}")
        return

    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce

    client = TradingClient(KEY, SECRET, paper=True)
    acct = client.get_account()
    print(f"Alpaca PAPER · кэш ${float(acct.cash):,.2f} · портфель ${float(acct.portfolio_value):,.2f}")
    positions = {p.symbol: p for p in client.get_all_positions()}
    print("-" * 56)

    compare_only = "--compare" in sys.argv
    for tk, (pos, txt, price) in sig.items():
        want_long = pos == 1
        holding = tk in positions
        if compare_only:
            print(f"  {tk:6} {txt:20} {'(держим)' if holding else ''}")
            continue
        try:
            if want_long and not holding:
                client.submit_order(MarketOrderRequest(
                    symbol=tk, notional=config.POSITION_USD,
                    side=OrderSide.BUY, time_in_force=TimeInForce.DAY))
                print(f"  {tk:6} {txt:20} ✅ КУПИЛ ${config.POSITION_USD:g}")
            elif not want_long and holding:
                client.close_position(tk)
                print(f"  {tk:6} {txt:20} ✅ ПРОДАЛ")
            else:
                print(f"  {tk:6} {txt:20} держим")
        except Exception as e:
            print(f"  {tk:6} {txt:20} ⚠️ {type(e).__name__}: {str(e)[:45]}")


if __name__ == "__main__":
    main()
