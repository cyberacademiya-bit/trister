# -*- coding: utf-8 -*-
"""
Подключение к бирже (Binance).
Ключи берутся из .env. Флаг TESTNET в config.py решает: демо или реал.

    config.TESTNET = True  → демо-счёт (testnet.binance.vision), игрушечные деньги
    config.TESTNET = False → реальные деньги (НЕ включать, пока бот не готов)
"""
import os

import ccxt
from dotenv import load_dotenv

import config

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Адрес нового Binance Spot Demo (demo.binance.com). НЕ старый testnet.binance.vision.
DEMO_SPOT_URL = "https://demo-api.binance.com/api/v3"


def get_exchange():
    key = os.getenv("BINANCE_API_KEY")
    secret = os.getenv("BINANCE_API_SECRET")
    if not key or not secret:
        raise RuntimeError("Нет ключей! Проверь файл .env (BINANCE_API_KEY / BINANCE_API_SECRET).")

    exchange = ccxt.binance({
        "apiKey": key,
        "secret": secret,
        "enableRateLimit": True,
        "options": {
            "defaultType": "spot",
            "adjustForTimeDifference": True,   # чинит ошибки времени (частая беда)
        },
    })

    if config.TESTNET:
        # перенаправляем спотовые запросы на демо-сервер Binance
        exchange.urls["api"]["public"] = DEMO_SPOT_URL
        exchange.urls["api"]["private"] = DEMO_SPOT_URL
        # у демо нет служебных sapi-эндпоинтов (валюты, маржа, фьючерсы) —
        # грузим ТОЛЬКО спот, остальное не трогаем
        exchange.has["fetchCurrencies"] = False
        exchange.options["fetchMarkets"]["types"] = ["spot"]
        exchange.options["fetchMargins"] = False

    return exchange
