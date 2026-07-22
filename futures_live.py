# -*- coding: utf-8 -*-
"""
ЖИВОЙ фьючерсный бот — ЛОНГ/ШОРТ по 5-минутному анализу, в реальном времени.
Анализ: EMA20/EMA50 + RSI на 5m свечах. Риск: стоп-лосс 2%. Размер: $1000.
Только ДЕМО. Запуск с Мака (Binance тут доступен):

    python futures_live.py            → крутится в цикле, проверяет каждые 60 сек
    python futures_live.py --once     → один проход (для теста)
"""
import sys
import time
from datetime import datetime, timezone, timedelta

from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator

import data
import futures_broker as fb
import journal

BISHKEK = timezone(timedelta(hours=6))

SYMBOLS = ["BTC/USDT", "ETH/USDT"]   # перпетуалы
TIMEFRAME = "5m"                     # анализ на 5-минутных свечах
NOTIONAL_USD = 1000                  # размер позиции (демо)
LEVERAGE = 2                         # плечо
STOP_PCT = 0.02                      # стоп-лосс 2% (риск-менеджмент)
CHECK_SEC = 60                       # проверка риска в реальном времени, сек


def analyze(df):
    """Лонг/шорт сигнал по 5m: тренд (EMA20 vs EMA50) + фильтр RSI (не входить в перегрев)."""
    c = df["close"]
    ef = EMAIndicator(c, 20).ema_indicator().iloc[-1]
    es = EMAIndicator(c, 50).ema_indicator().iloc[-1]
    rsi = RSIIndicator(c, 14).rsi().iloc[-1]
    if ef > es and rsi < 75:
        return "long", f"EMA↑ RSI {rsi:.0f}"
    if ef < es and rsi > 25:
        return "short", f"EMA↓ RSI {rsi:.0f}"
    return "flat", f"нейтрально RSI {rsi:.0f}"


def get_pos(ex, sym):
    for p in ex.fetch_positions([sym]):
        amt = abs(float(p.get("contracts") or 0))
        if amt > 0:
            return p.get("side"), amt, float(p.get("entryPrice") or 0)
    return None, 0.0, 0.0


def open_pos(ex, sym, direction, price):
    try:
        ex.set_leverage(LEVERAGE, sym)
    except Exception:
        pass
    amt = float(ex.amount_to_precision(sym, NOTIONAL_USD / price))
    if direction == "long":
        ex.create_market_buy_order(sym, amt)
    else:
        ex.create_market_sell_order(sym, amt)


def close_pos(ex, sym, side, amt):
    try:
        ex.cancel_all_orders(sym)
    except Exception:
        pass
    if side == "long":
        ex.create_market_sell_order(sym, amt, {"reduceOnly": True})
    else:
        ex.create_market_buy_order(sym, amt, {"reduceOnly": True})


def tick(ex):
    now = datetime.now(BISHKEK).strftime("%H:%M:%S")
    for sym in SYMBOLS:
        try:
            df = data.fetch_ohlcv(symbol=sym, timeframe=TIMEFRAME, days=3, use_cache=False)
            want, why = analyze(df)
            side, amt, entry = get_pos(ex, sym)
            price = ex.fetch_ticker(sym)["last"]

            # 1) РИСК: стоп-лосс в реальном времени
            if side and entry:
                loss = (price - entry) / entry if side == "short" else (entry - price) / entry
                if loss >= STOP_PCT:
                    close_pos(ex, sym, side, amt)
                    journal.log("СТОП-ЛОСС", signal=f"{sym} {side}", price=price,
                                note=f"−{loss*100:.1f}% (live 5m)")
                    print(f"  {now} {sym:12} 🛑 СТОП −{loss*100:.1f}% — закрыл {side}")
                    side, entry = None, 0

            # 2) ЛОГИКА: открыть/перевернуть/держать
            if want == "flat":
                if side:
                    close_pos(ex, sym, side, amt)
                    print(f"  {now} {sym:12} ⚪ {why:16} закрыл {side}")
                else:
                    print(f"  {now} {sym:12} ⚪ {why:16} вне рынка")
            elif want != side:
                if side:
                    close_pos(ex, sym, side, amt)
                open_pos(ex, sym, want, price)
                journal.log(f"LIVE ОТКРЫЛ {want}", signal=f"{sym} {why}", price=price,
                            cost_usdt=NOTIONAL_USD, note=f"5m, плечо {LEVERAGE}x, стоп {STOP_PCT*100:.0f}%")
                arrow = "🟢 ЛОНГ" if want == "long" else "🔴 ШОРТ"
                print(f"  {now} {sym:12} {arrow} {why:16} @ {price}")
            elif side:
                pnl = (price - entry) / entry * 100 * (1 if side == "long" else -1)
                print(f"  {now} {sym:12} держим {side:5} {why:16} PnL {pnl:+.2f}%")
        except Exception as e:
            print(f"  {now} {sym:12} ⚠️ {type(e).__name__}: {str(e)[:45]}")


def main():
    if not fb.has_keys():
        print("⚠️ Нет ключей фьючерсного демо (.env: FUTURES_KEY/FUTURES_SECRET).")
        return
    ex = fb.get_futures_exchange()
    bal = ex.fetch_balance()["total"].get("USDT", 0)
    print(f"🔴🟢 ЖИВОЙ ЛОНГ/ШОРТ · 5m · ${NOTIONAL_USD} · плечо {LEVERAGE}x · стоп {STOP_PCT*100:.0f}% · баланс {bal:.2f} USDT")
    print(f"Проверка каждые {CHECK_SEC} сек. Ctrl+C для остановки.")
    print("-" * 64)

    once = "--once" in sys.argv
    while True:
        try:
            tick(ex)
        except Exception as e:
            print(f"  ⚠️ цикл: {str(e)[:60]}")
        if once:
            break
        print("-" * 64)
        time.sleep(CHECK_SEC)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️ Остановлено.")
