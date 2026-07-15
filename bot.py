# -*- coding: utf-8 -*-
"""
АВТОПИЛОТ «Тристер» — робот торгует сам на демо-счёте.

Запуск:
    python bot.py --once     → один проход (проверить, что всё работает)
    python bot.py            → бесконечный цикл (проверяет рынок раз в CHECK_INTERVAL_SEC)

Логика (long-only): быстрая SMA выше медленной → держим BTC, иначе → в USDT.
Каждое действие пишется в trades.csv.
"""
import sys
import time
from datetime import datetime

import pandas as pd

import broker
import config
import strategy
import executor
import journal

BASE = config.SYMBOL.split("/")[0]   # 'BTC'


def latest_signal(ex):
    """Тянет свежие свечи с биржи и возвращает (сигнал 0/1, цена закрытия)."""
    ohlcv = ex.fetch_ohlcv(config.SYMBOL, config.TIMEFRAME, limit=config.SLOW + 50)
    df = pd.DataFrame(ohlcv, columns=["ts", "open", "high", "low", "close", "volume"])
    df = strategy.sma_crossover(df)
    return int(df["position"].iloc[-1]), float(df["close"].iloc[-1])


def position(ex):
    """Сколько BTC держим и на сколько $ (чтобы понять — в позиции мы или нет)."""
    bal = ex.fetch_balance()["total"]
    btc = float(bal.get(BASE, 0) or 0)
    price = ex.fetch_ticker(config.SYMBOL)["last"]
    return btc, btc * price


def tick(ex):
    """Один цикл принятия решения."""
    signal, close = latest_signal(ex)
    btc, btc_value = position(ex)
    holding = btc_value >= config.MIN_POSITION_USD

    state = "в позиции (BTC)" if holding else "вне рынка (USDT)"
    sig_txt = "ВВЕРХ ↑" if signal == 1 else "ВНИЗ ↓"
    print(f"[{datetime.now():%H:%M:%S}] сигнал: {sig_txt} | сейчас: {state} | цена {close:.2f}")

    if signal == 1 and not holding:
        print(f"  → ПОКУПАЮ на ${config.POSITION_USD:g}")
        order = executor.market_buy(config.POSITION_USD, ex=ex)
        journal.log("BUY", signal, order.get("average") or close,
                    order.get("filled"), order.get("cost"), "сигнал вверх, входим")

    elif signal == 0 and holding:
        print(f"  → ПРОДАЮ {btc} BTC")
        order = executor.market_sell(btc, ex=ex)
        journal.log("SELL", signal, order.get("average") or close,
                    order.get("filled"), order.get("cost"), "сигнал вниз, выходим")

    else:
        print("  → держим как есть (действий нет)")
        journal.log("HOLD", signal, close, btc, btc_value, state)


def main():
    if not config.TESTNET:
        print("⛔ TESTNET=False — это РЕАЛЬНЫЙ счёт. Автопилот остановлен для безопасности.")
        return

    once = "--once" in sys.argv
    ex = broker.get_exchange()

    print("=" * 52)
    print(f"  АВТОПИЛОТ ТРИСТЕР | {config.SYMBOL} {config.TIMEFRAME} | ДЕМО")
    print(f"  Сделка: ${config.POSITION_USD:g} | Проверка: раз в {config.CHECK_INTERVAL_SEC}с")
    print("=" * 52)

    if once:
        tick(ex)
        return

    while True:
        try:
            tick(ex)
        except Exception as e:
            print(f"  ⚠️ ошибка в цикле: {e}")
            journal.log("ERROR", note=str(e))
        time.sleep(config.CHECK_INTERVAL_SEC)


if __name__ == "__main__":
    main()
