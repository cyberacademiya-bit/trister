# -*- coding: utf-8 -*-
"""
Тест реальных сделок на демо: покупает BTC на $5 и на $10, показывает баланс.
Запуск:  python first_trade.py            → купит на 5 и на 10
         python first_trade.py 25         → купит на 25
"""
import sys

import broker
import config
import executor


def buy(ex, usd):
    print(f"\n>>> Покупаю BTC на ${usd:g} по рынку...")
    order = executor.market_buy(usd, config.SYMBOL, ex)
    filled = order.get("filled")
    avg = order.get("average") or order.get("price")
    cost = order.get("cost")
    print(f"    ✅ ордер #{order.get('id')}: куплено {filled} BTC по ~{avg}, потрачено {cost} USDT")


def main():
    if not config.TESTNET:
        print("⛔ TESTNET=False — это РЕАЛЬНЫЙ счёт. Отмена.")
        return

    amounts = [float(a) for a in sys.argv[1:]] or [5.0, 10.0]

    ex = broker.get_exchange()
    print("Баланс ДО:", executor.balances(ex))
    print(f"Цена BTC сейчас: {executor.price(config.SYMBOL, ex)} USDT")

    for usd in amounts:
        buy(ex, usd)

    print("\nБаланс ПОСЛЕ:", executor.balances(ex))
    print("\n🤖 Готово — бот реально совершил сделки на демо-счёте.")


if __name__ == "__main__":
    main()
