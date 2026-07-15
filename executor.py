# -*- coding: utf-8 -*-
"""
Исполнение сделок: покупка/продажа по рынку на демо-счёте.
Всё уважает фильтры биржи (минимальный размер, точность) через ccxt.
"""
import broker
import config


def balances(ex=None):
    """Ненулевые балансы: {'USDT': 5000.0, 'BTC': 0.003, ...}"""
    ex = ex or broker.get_exchange()
    total = ex.fetch_balance()["total"]
    return {c: a for c, a in total.items() if a and a > 0}


def price(symbol=None, ex=None):
    ex = ex or broker.get_exchange()
    return ex.fetch_ticker(symbol or config.SYMBOL)["last"]


def market_buy(quote_amount, symbol=None, ex=None):
    """Купить по рынку РОВНО на quote_amount USDT (через quoteOrderQty биржи).
    Так биржа сама считает количество BTC — не срываемся на округлении копеек."""
    ex = ex or broker.get_exchange()
    symbol = symbol or config.SYMBOL
    ex.load_markets()
    min_cost = ex.market(symbol)["limits"]["cost"]["min"] or 5.0
    if quote_amount < min_cost:
        raise ValueError(f"Сумма {quote_amount}$ ниже минимума биржи {min_cost}$ — сделка не пройдёт.")
    return ex.create_market_buy_order_with_cost(symbol, quote_amount)


def market_sell(amount, symbol=None, ex=None):
    """Продать по рынку amount базовой монеты (BTC). Возвращает ордер."""
    ex = ex or broker.get_exchange()
    symbol = symbol or config.SYMBOL
    ex.load_markets()
    amount = float(ex.amount_to_precision(symbol, amount))
    return ex.create_market_sell_order(symbol, amount)
