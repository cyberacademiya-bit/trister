# -*- coding: utf-8 -*-
"""
Демо-бот на ЛОКАЛЬНОМ счёте — торгует ВСЕ рынки виртуальными деньгами по живым ценам.
Никакого брокера/KYC. Стратегия — из config.STRATEGY.

  python paper_trader.py            → один проход (торгует по сигналам)
  python paper_trader.py --status   → показать портфель, ничего не трогать
  python paper_trader.py --reset    → сбросить счёт к $10 000
"""
import sys
from datetime import datetime, timezone, timedelta

import pandas as pd
import yfinance as yf

BISHKEK = timezone(timedelta(hours=6))   # время Кыргызстана (GMT+6)

import config
import paper
import strategies

# Все рынки, которые торгуем виртуально (yfinance-тикеры)
MARKETS = {
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "Nvidia", "TSLA": "Tesla",
    "AMZN": "Amazon", "GOOGL": "Google", "META": "Meta", "SPY": "S&P 500",
    "QQQ": "Nasdaq", "GC=F": "Золото", "SI=F": "Серебро", "PL=F": "Платина",
    "CL=F": "Нефть WTI", "HG=F": "Медь", "BTC-USD": "Bitcoin", "ETH-USD": "Ethereum",
}


def fetch():
    """Скачивает свечи всех рынков; возвращает {symbol: (signal, price)}."""
    raw = yf.download(list(MARKETS), start="2023-01-01", progress=False, auto_adjust=True, group_by="ticker")
    out = {}
    for tk in MARKETS:
        try:
            d = raw[tk].dropna().reset_index()
            d.columns = [str(c).lower() for c in d.columns]
            d = d.rename(columns={"date": "dt"})
            df = d[["dt", "open", "high", "low", "close"]]
            if len(df) < 210:
                continue
            pos, txt, _ = strategies.signal_now(config.STRATEGY, df)
            out[tk] = (pos, float(df["close"].iloc[-1]), txt)
        except Exception:
            pass
    return out


def show(acc, prices):
    total = paper.value(acc, prices)
    pnl = total - acc.get("start", 10000)
    print(f"\n💼 ЛОКАЛЬНЫЙ ДЕМО-СЧЁТ")
    print(f"  Кэш: ${acc['cash']:,.2f}")
    if acc["positions"]:
        print("  Позиции:")
        for s, pos in acc["positions"].items():
            cur = pos["qty"] * prices.get(s, 0)
            p = cur - pos["cost"]
            print(f"    {MARKETS.get(s, s):12} ${cur:8,.2f}  ({p:+.2f})")
    print(f"  ─────────────────────────")
    print(f"  ИТОГО: ${total:,.2f}   (старт $10,000 · {pnl:+,.2f} · {(total/acc.get('start',10000)-1)*100:+.2f}%)")


def main():
    acc = paper.load()

    if "--reset" in sys.argv:
        acc = {"cash": paper.START_CASH, "start": paper.START_CASH, "positions": {}, "history": []}
        paper.save(acc)
        print("✅ Счёт сброшен к $10 000.")
        return

    print(f"Тяну живые цены всех рынков (стратегия '{config.STRATEGY}')...")
    sig = fetch()
    prices = {s: v[1] for s, v in sig.items()}

    if "--status" in sys.argv:
        show(acc, prices)
        return

    now = datetime.now(BISHKEK).strftime("%Y-%m-%d %H:%M")
    print(f"\n📈 ТОРГУЮ по сигналам ({now}):")
    print("-" * 58)
    for tk, (pos, price, txt) in sig.items():
        want_long = pos == 1
        holding = tk in acc["positions"]
        name = MARKETS.get(tk, tk)
        if want_long and not holding:
            if paper.buy(acc, tk, config.POSITION_USD, price, now):
                print(f"  {name:12} {txt:18} ✅ КУПИЛ ${config.POSITION_USD:g}")
        elif not want_long and holding:
            paper.sell(acc, tk, price, now)
            print(f"  {name:12} {txt:18} ✅ ПРОДАЛ")
        else:
            print(f"  {name:12} {txt:18} держим")
    print("-" * 58)
    paper.save(acc)
    show(acc, prices)


if __name__ == "__main__":
    main()
