# -*- coding: utf-8 -*-
"""
КРУПНАЯ ЗАКУПКА — акции + облигации (ETF) на Alpaca и локальном симуляторе.
Диверсифицированный портфель на большие суммы. Только ДЕМО.

    python buy_basket.py
"""
import os
from datetime import datetime, timezone, timedelta

BISHKEK = timezone(timedelta(hours=6))

# Акции (крупные компании США)
STOCKS = {
    "AAPL": "Apple", "MSFT": "Microsoft", "NVDA": "Nvidia", "GOOGL": "Google",
    "AMZN": "Amazon", "META": "Meta", "SPY": "S&P 500", "QQQ": "Nasdaq 100",
}
# Облигации — через фонды (ETF). Настоящие облигации, торгуемые как акции.
BONDS = {
    "TLT": "Гособлигации США 20+ лет", "IEF": "Гособлигации США 7-10 лет",
    "AGG": "Все облигации США", "BND": "Весь рынок облигаций", "LQD": "Корпоративные облигации",
}

ALPACA_USD = 3000    # крупно: $3000 на инструмент (счёт $100k)
LOCAL_USD = 500      # локальный счёт меньше ($10k) → $500 на инструмент


def buy_alpaca():
    print("═══ Alpaca — акции + облигации ($3000 каждая) ═══")
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
    key, secret = os.getenv("ALPACA_KEY"), os.getenv("ALPACA_SECRET")
    if not key:
        print("  ⚠️ нет ключей Alpaca"); return
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import MarketOrderRequest
    from alpaca.trading.enums import OrderSide, TimeInForce
    client = TradingClient(key, secret, paper=True)
    for tk, name in {**STOCKS, **BONDS}.items():
        try:
            client.submit_order(MarketOrderRequest(
                symbol=tk, notional=ALPACA_USD, side=OrderSide.BUY, time_in_force=TimeInForce.DAY))
            print(f"  ✅ {tk:5} {name:26} ${ALPACA_USD}")
        except Exception as e:
            print(f"  ⚠️ {tk:5} {str(e)[:50]}")
    print("  ⏳ Если биржа США закрыта — ордера исполнятся на открытии (19:30 Бишкек).")


def buy_local():
    print("═══ Локальный симулятор — акции + облигации ($500 каждая) ═══")
    import paper
    import yfinance as yf
    acc = paper.load()
    now = datetime.now(BISHKEK).strftime("%Y-%m-%d %H:%M")
    tickers = list(STOCKS) + list(BONDS)
    raw = yf.download(tickers, period="5d", progress=False, auto_adjust=True, group_by="ticker")
    bought = 0
    for tk in tickers:
        try:
            px = float(raw[tk]["Close"].dropna().iloc[-1])
        except Exception:
            continue
        if paper.buy(acc, tk, LOCAL_USD, px, now):
            name = {**STOCKS, **BONDS}[tk]
            print(f"  ✅ {tk:5} {name:26} ${LOCAL_USD}  (${px:.2f})")
            bought += 1
    paper.save(acc)
    print(f"  Куплено: {bought} · кэш остался: ${acc['cash']:,.2f}")


if __name__ == "__main__":
    print("🛒 КРУПНАЯ ЗАКУПКА: акции + облигации (демо)\n")
    buy_alpaca()
    print()
    buy_local()
    print("\n✅ Готово. Обнови дашборд: python gather_data.py")
