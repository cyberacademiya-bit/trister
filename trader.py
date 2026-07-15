# -*- coding: utf-8 -*-
"""
ЕДИНЫЙ бот «Тристер» — доступ ко ВСЕМ стратегиям сразу.

  python trader.py --compare        → показать, что каждая стратегия говорит СЕЙЧАС
  python trader.py                  → торговать стратегией из config.STRATEGY
  python trader.py --strategy cot   → торговать конкретной (разово)
  python trader.py --loop           → автопилот (проверка раз в CHECK_INTERVAL_SEC)

Примечание: спот PAXG нельзя шортить. Если стратегия говорит МЕДВЕДЬ (-1),
на споте бот уходит в кэш (0). Шорт возможен только на фьючерсах.
"""
import sys
import time
from datetime import datetime

import pandas as pd

import broker
import config
import data
import executor
import journal
import strategies

BASE = config.SYMBOL.split("/")[0]
COT_FILE = "Данные/gold_williams_cot_index.csv"


def get_data():
    ohlc = data.fetch_ohlcv(symbol=config.SYMBOL, timeframe="1d", days=400, use_cache=False)
    try:
        cot_index = float(pd.read_csv(COT_FILE)["williams_cot_index"].dropna().iloc[-1])
    except Exception:
        cot_index = None
    return ohlc, cot_index


def compare(ohlc, cot_index):
    print(f"\n📋 ЧТО ГОВОРЯТ ВСЕ СТРАТЕГИИ СЕЙЧАС ({config.SYMBOL}, {datetime.now():%Y-%m-%d %H:%M})")
    print("-" * 62)
    for name, (title, fn, kind) in strategies.REGISTRY.items():
        pos, txt, _ = strategies.signal_now(name, ohlc, cot_index)
        note = "  → на споте = кэш" if pos == -1 else ""
        active = " ⬅ АКТИВНАЯ" if name == config.STRATEGY else ""
        print(f"  {title:30} {txt:20}{note}{active}")
    print("-" * 62)
    print(f"  Активная (config.STRATEGY): '{config.STRATEGY}'. Сменить — в config.py.")


def tick(ex, strategy, ohlc, cot_index):
    title, fn, kind = strategies.REGISTRY[strategy]
    pos, txt, row = strategies.signal_now(strategy, ohlc, cot_index)
    want_long = pos == 1                     # спот: только лонг или кэш (шорт → кэш)

    bal = ex.fetch_balance()["total"]
    amt = float(bal.get(BASE, 0) or 0)
    price = ex.fetch_ticker(config.SYMBOL)["last"]
    holding = amt * price >= config.MIN_POSITION_USD

    print(f"\n[{datetime.now():%Y-%m-%d %H:%M}] Стратегия: {title}")
    print(f"  Сигнал: {txt}" + ("  (шорт недоступен на споте → кэш)" if pos == -1 else ""))
    print(f"  Сейчас: {'в золоте' if holding else 'в USDT'} ({amt:.5f} {BASE})")

    if want_long and not holding:
        o = executor.market_buy(config.POSITION_USD, ex=ex)
        journal.log("BUY", pos, o.get("average") or price, o.get("filled"), o.get("cost"), f"{strategy}: вход")
        print(f"  → ✅ КУПИЛ на ${config.POSITION_USD:g}: {o.get('filled')} {BASE}")
    elif not want_long and holding:
        o = executor.market_sell(amt, ex=ex)
        journal.log("SELL", pos, o.get("average") or price, o.get("filled"), o.get("cost"), f"{strategy}: выход")
        print(f"  → ✅ ПРОДАЛ, получено {o.get('cost')} USDT")
    else:
        journal.log("HOLD", pos, price, amt, amt * price, f"{strategy}: без действий")
        print(f"  → держим как есть")


def universe_tick(ex, strategy):
    """Портфельный режим: сканирует всю крипто-вселенную и торгует лонги."""
    bal = ex.fetch_balance()["total"]
    try:
        gold_cot = float(pd.read_csv(COT_FILE)["williams_cot_index"].dropna().iloc[-1])
    except Exception:
        gold_cot = None
    print(f"\n📦 ПОРТФЕЛЬ КРИПТЫ · стратегия '{strategy}' · {len(config.CRYPTO_UNIVERSE)} инструментов")
    print("-" * 60)
    for sym in config.CRYPTO_UNIVERSE:
        base = sym.split("/")[0]
        try:
            ohlc = data.fetch_ohlcv(symbol=sym, timeframe="1d", days=400, use_cache=False)
            ci = gold_cot if base in ("PAXG", "XAUT") else None
            pos, txt, _ = strategies.signal_now(strategy, ohlc, ci)
            want_long = pos == 1
            amt = float(bal.get(base, 0) or 0)
            price = ex.fetch_ticker(sym)["last"]
            holding = amt * price >= config.MIN_POSITION_USD
            act = "держим"
            if want_long and not holding:
                o = executor.market_buy(config.POSITION_USD, symbol=sym, ex=ex)
                journal.log("BUY", pos, o.get("average") or price, o.get("filled"), o.get("cost"), f"{strategy} {sym}")
                act = f"✅ КУПИЛ ${config.POSITION_USD:g}"
            elif not want_long and holding:
                o = executor.market_sell(amt, symbol=sym, ex=ex)
                journal.log("SELL", pos, o.get("average") or price, o.get("filled"), o.get("cost"), f"{strategy} {sym}")
                act = "✅ ПРОДАЛ"
            print(f"  {sym:12} {txt:20} {act}")
        except Exception as e:
            print(f"  {sym:12} ошибка: {type(e).__name__}")
    print("-" * 60)


def main():
    ohlc, cot_index = get_data()

    if "--compare" in sys.argv:
        compare(ohlc, cot_index)
        return

    strategy = config.STRATEGY
    if "--strategy" in sys.argv:
        strategy = sys.argv[sys.argv.index("--strategy") + 1]
    if strategy not in strategies.REGISTRY:
        print(f"Неизвестная стратегия '{strategy}'. Доступно: {list(strategies.REGISTRY)}")
        return
    if not config.TESTNET:
        print("⛔ TESTNET=False — реальный счёт. Стоп.")
        return

    ex = broker.get_exchange()
    print("=" * 56)
    print(f"  ЕДИНЫЙ БОТ · {config.SYMBOL} · ДЕМО · ${config.POSITION_USD:g}")
    print("=" * 56)

    if "--universe" in sys.argv:
        universe_tick(ex, strategy)
        return

    if "--loop" not in sys.argv:
        tick(ex, strategy, ohlc, cot_index)
        return
    while True:
        try:
            ohlc, cot_index = get_data()
            tick(ex, strategy, ohlc, cot_index)
        except Exception as e:
            print(f"  ⚠️ ошибка: {e}")
        time.sleep(config.CHECK_INTERVAL_SEC)


def _is_geoblock(err):
    s = str(err).lower()
    return "451" in s or "restricted location" in s or "eligibility" in s


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if _is_geoblock(e):
            print("ℹ️  Binance недоступен с этого сервера (гео-блок 451). "
                  "Крипта+золото торгуются на локальном симуляторе и с Мака. Пропускаю.")
            sys.exit(0)   # не роняем прогон — это ограничение Binance, а не ошибка бота
        raise
