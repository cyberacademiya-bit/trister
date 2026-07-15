# -*- coding: utf-8 -*-
"""
Проверка связи: подключается к демо-счёту и показывает баланс.
Запуск:  python test_connection.py
"""
import broker
import config


def main():
    mode = "ДЕМО (Testnet)" if config.TESTNET else "!!! РЕАЛЬНЫЙ СЧЁТ !!!"
    print(f"Режим: {mode}")
    print("Подключаюсь к Binance...")

    ex = broker.get_exchange()
    bal = ex.fetch_balance()

    print("✅ Связь есть! Бот видит твой демо-счёт.\n")
    print("Баланс (только ненулевое):")
    print("-" * 32)
    found = False
    for coin, amount in bal["total"].items():
        if amount and amount > 0:
            print(f"  {coin:<6} : {amount}")
            found = True
    if not found:
        print("  (пусто — демо-счёт без монет)")
    print("-" * 32)

    # заодно проверим, что видим живую цену
    ticker = ex.fetch_ticker(config.SYMBOL)
    print(f"\nТекущая цена {config.SYMBOL}: {ticker['last']} USDT")


if __name__ == "__main__":
    main()
