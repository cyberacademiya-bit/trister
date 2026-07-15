# -*- coding: utf-8 -*-
"""
Загрузка исторических свечей (OHLCV) с биржи через ccxt.
Данные кэшируются в data_cache/, чтобы не дёргать биржу каждый раз.
"""
import os
import time
import ccxt
import pandas as pd

import config

CACHE_DIR = os.path.join(os.path.dirname(__file__), "data_cache")


def fetch_ohlcv(symbol=None, timeframe=None, days=None, use_cache=True):
    """Возвращает DataFrame со столбцами: ts, open, high, low, close, volume, dt."""
    symbol = symbol or config.SYMBOL
    timeframe = timeframe or config.TIMEFRAME
    days = days or config.SINCE_DAYS

    os.makedirs(CACHE_DIR, exist_ok=True)
    safe = symbol.replace("/", "")
    cache_file = os.path.join(CACHE_DIR, f"{config.EXCHANGE}_{safe}_{timeframe}_{days}d.csv")

    if use_cache and os.path.exists(cache_file):
        return pd.read_csv(cache_file, parse_dates=["dt"])

    exchange = getattr(ccxt, config.EXCHANGE)({"enableRateLimit": True})
    since = exchange.milliseconds() - days * 24 * 60 * 60 * 1000
    limit = 1000
    all_rows = []

    while True:
        batch = exchange.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        if not batch:
            break
        all_rows += batch
        since = batch[-1][0] + 1          # следующая пачка с последней свечи
        if len(batch) < limit:
            break
        time.sleep(exchange.rateLimit / 1000)  # уважаем лимиты биржи

    df = pd.DataFrame(all_rows, columns=["ts", "open", "high", "low", "close", "volume"])
    df = df.drop_duplicates(subset="ts").reset_index(drop=True)
    df["dt"] = pd.to_datetime(df["ts"], unit="ms")
    df.to_csv(cache_file, index=False)
    return df


if __name__ == "__main__":
    d = fetch_ohlcv(use_cache=False)
    print(f"Загружено {len(d)} свечей: {d['dt'].iloc[0]} → {d['dt'].iloc[-1]}")
