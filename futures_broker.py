# -*- coding: utf-8 -*-
"""
Подключение к Binance FUTURES Testnet (демо фьючерсов, где можно ШОРТИТЬ с плечом).
Ключи в .env:  FUTURES_KEY=...  FUTURES_SECRET=...
Это ОТДЕЛЬНЫЙ демо от спота — ключи с testnet.binancefuture.com.
"""
import os

import ccxt
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))


def get_futures_exchange():
    key = os.getenv("FUTURES_KEY")
    secret = os.getenv("FUTURES_SECRET")
    if not key or not secret:
        raise RuntimeError("Нет ключей фьючерсов в .env (FUTURES_KEY / FUTURES_SECRET).")
    ex = ccxt.binance({
        "apiKey": key,
        "secret": secret,
        "enableRateLimit": True,
        "options": {"defaultType": "future", "adjustForTimeDifference": True},
    })
    # ccxt убрал sandbox для фьючерсов → вручную указываем демо-эндпоинт Binance
    for k in list(ex.urls["api"].keys()):
        if k.startswith("fapi"):
            ex.urls["api"][k] = ex.urls["api"][k].replace(
                "https://fapi.binance.com", "https://demo-fapi.binance.com")
    ex.has["fetchCurrencies"] = False
    ex.options["fetchMarkets"] = ["linear"]   # только USDT-M фьючерсы
    return ex


def has_keys():
    return bool(os.getenv("FUTURES_KEY") and os.getenv("FUTURES_SECRET"))
