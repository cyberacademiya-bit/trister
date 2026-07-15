# -*- coding: utf-8 -*-
"""
УМНЫЙ бот «Тристер» — торгует золото (PAXG/USDT) на демо.
Решения принимает МОЗГ из brain.py (проверенная логика: тренд + защита от крахов).

Запуск:  python smart_bot.py         → одно решение сейчас
         python smart_bot.py --loop  → крутиться (проверка раз в CHECK_INTERVAL_SEC)
"""
import sys
import time
from datetime import datetime

import pandas as pd

import brain
import broker
import config
import data
import executor
import journal

BASE = config.SYMBOL.split("/")[0]  # PAXG
COT_FILE = "Данные/gold_williams_cot_index.csv"


def current_signal():
    """Тянет дневные свечи + COT и спрашивает мозг, что делать."""
    px = data.fetch_ohlcv(symbol=config.SYMBOL, timeframe="1d", days=400, use_cache=False)
    try:
        cot = pd.read_csv(COT_FILE)
        cot_index = float(cot["williams_cot_index"].dropna().iloc[-1])
    except Exception:
        cot_index = None
    return brain.live_signal(px, cot_index)


def tick(ex):
    go_long, s = current_signal()

    bal = ex.fetch_balance()["total"]
    paxg = float(bal.get(BASE, 0) or 0)
    price = ex.fetch_ticker(config.SYMBOL)["last"]
    holding = paxg * price >= config.MIN_POSITION_USD
    cot_txt = f"{s['cot_index']:.0f}%" if s["cot_index"] is not None else "н/д"

    print(f"\n[{datetime.now():%Y-%m-%d %H:%M}] РЕШЕНИЕ ПО ЗОЛОТУ (мозг: тренд)")
    print(f"  Цена {s['price']:.2f} | MA50 {s['ma50']:.2f} | MA200 {s['ma200']:.2f}")
    print(f"  Тренд MA50>MA200: {'✅' if s['trend_up'] else '❌'}   Цена>MA200: {'✅' if s['above_long'] else '❌'}")
    print(f"  COT (справочно, {'вкл' if s['use_cot'] else 'выкл'}): {cot_txt}")
    print(f"  Сигнал: {'🟢 ЛОНГ (держать золото)' if go_long else '⚪ ВНЕ РЫНКА (кэш)'}")
    print(f"  Сейчас: {'в золоте' if holding else 'в USDT'} ({paxg:.5f} {BASE})")

    if go_long and not holding:
        print(f"  → ПОКУПАЮ золото на ${config.POSITION_USD:g}")
        o = executor.market_buy(config.POSITION_USD, ex=ex)
        journal.log("BUY", int(go_long), o.get("average") or price, o.get("filled"), o.get("cost"),
                    "тренд вверх: вход в золото")
        print(f"    ✅ куплено {o.get('filled')} {BASE} за {o.get('cost')} USDT")
    elif not go_long and holding:
        print(f"  → ПРОДАЮ золото (уходим в кэш)")
        o = executor.market_sell(paxg, ex=ex)
        journal.log("SELL", int(go_long), o.get("average") or price, o.get("filled"), o.get("cost"),
                    "режим неблагоприятный: выход в USDT")
        print(f"    ✅ продано, получено {o.get('cost')} USDT")
    else:
        print(f"  → ДЕРЖИМ как есть (действий нет)")
        journal.log("HOLD", int(go_long), price, paxg, paxg * price, "сигнал совпадает с позицией")


def main():
    if not config.TESTNET:
        print("⛔ TESTNET=False — реальный счёт. Стоп.")
        return
    ex = broker.get_exchange()
    print("=" * 56)
    print(f"  УМНЫЙ БОТ · {config.SYMBOL} · ДЕМО · сделка ${config.POSITION_USD:g}")
    print(f"  Мозг: тренд(MA50>MA200 + цена>MA200), защита от крахов")
    print("=" * 56)

    if "--loop" not in sys.argv:
        tick(ex)
        return
    while True:
        try:
            tick(ex)
        except Exception as e:
            print(f"  ⚠️ ошибка: {e}")
        time.sleep(config.CHECK_INTERVAL_SEC)


if __name__ == "__main__":
    main()
