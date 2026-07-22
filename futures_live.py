# -*- coding: utf-8 -*-
"""
ЖИВОЙ фьючерсный бот — ЛОНГ/ШОРТ по 5-минутному анализу, в реальном времени.
Анализ: EMA20/EMA50 + RSI на 5m. Риск: стоп-лосс 2%. Размер: $1000.
Публикует живое состояние в Данные/live_futures.json и обновляет дашборд.
Только ДЕМО. Запуск с Мака:

    python futures_live.py            → цикл, проверка каждые 60 сек
    python futures_live.py --once     → один проход
"""
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone, timedelta

from ta.trend import EMAIndicator
from ta.momentum import RSIIndicator

import data
import futures_broker as fb
import journal

BISHKEK = timezone(timedelta(hours=6))
HERE = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(HERE, "Данные", "live_futures.json")

SYMBOLS = ["BTC/USDT", "ETH/USDT"]
TIMEFRAME = "5m"
NOTIONAL_USD = 1000
LEVERAGE = 2
STOP_PCT = 0.02
CHECK_SEC = 60
SYNC_EVERY = 5          # обновлять сайт каждые N кругов (плюс сразу при сделке)

RECENT = []             # последние действия (для дашборда)


def analyze(df):
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


def publish(positions):
    """Пишет живое состояние в JSON — дашборд его показывает."""
    state = {"generated": datetime.now(BISHKEK).strftime("%Y-%m-%d %H:%M:%S") + " (Бишкек)",
             "size_usd": NOTIONAL_USD, "leverage": LEVERAGE, "stop_pct": STOP_PCT * 100,
             "positions": positions, "recent": RECENT[-8:][::-1]}
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        json.dump(state, open(STATE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    except Exception:
        pass


def sync_site():
    """Собирает дашборд и пушит на сайт (с Мака Binance доступен)."""
    try:
        subprocess.run([sys.executable, "gather_data.py"], cwd=HERE, timeout=120, capture_output=True)
        subprocess.run(["git", "add", "-A"], cwd=HERE, timeout=30, capture_output=True)
        subprocess.run(["git", "commit", "-m", "🔴🟢 live: живая торговля фьючерсами"],
                       cwd=HERE, timeout=30, capture_output=True)
        subprocess.run(["git", "pull", "--no-rebase", "--no-edit", "-X", "ours", "origin", "main"],
                       cwd=HERE, timeout=60, capture_output=True)
        subprocess.run(["git", "push"], cwd=HERE, timeout=60, capture_output=True)
    except Exception:
        pass


def tick(ex):
    now = datetime.now(BISHKEK).strftime("%H:%M:%S")
    positions, traded = [], False
    for sym in SYMBOLS:
        short = sym.replace("/USDT", "")
        try:
            df = data.fetch_ohlcv(symbol=sym, timeframe=TIMEFRAME, days=3, use_cache=False)
            want, why = analyze(df)
            side, amt, entry = get_pos(ex, sym)
            price = ex.fetch_ticker(sym)["last"]
            cur_side, cur_entry = side, entry

            # 1) РИСК: стоп-лосс в реальном времени
            if side and entry:
                loss = (price - entry) / entry if side == "short" else (entry - price) / entry
                if loss >= STOP_PCT:
                    close_pos(ex, sym, side, amt)
                    journal.log("СТОП-ЛОСС", signal=f"{sym} {side}", price=price, note=f"−{loss*100:.1f}% live")
                    act = f"{now} {short} 🛑 СТОП −{loss*100:.1f}% (закрыл {side})"
                    print("  " + act); RECENT.append(act); traded = True
                    cur_side, cur_entry = None, 0

            # 2) ЛОГИКА
            if want == "flat":
                if cur_side:
                    close_pos(ex, sym, cur_side, amt)
                    act = f"{now} {short} ⚪ закрыл {cur_side} (нейтрально)"
                    print("  " + act); RECENT.append(act); traded = True
                    cur_side, cur_entry = None, 0
                else:
                    print(f"  {now} {sym:12} ⚪ {why:16} вне рынка")
            elif want != cur_side:
                if cur_side:
                    close_pos(ex, sym, cur_side, amt)
                open_pos(ex, sym, want, price)
                journal.log(f"LIVE ОТКРЫЛ {want}", signal=f"{sym} {why}", price=price,
                            cost_usdt=NOTIONAL_USD, note=f"5m, плечо {LEVERAGE}x, стоп {STOP_PCT*100:.0f}%")
                arrow = "🟢 ЛОНГ" if want == "long" else "🔴 ШОРТ"
                act = f"{now} {short} {arrow} @ {price}"
                print(f"  {now} {sym:12} {arrow} {why:16} @ {price}"); RECENT.append(act); traded = True
                cur_side, cur_entry = want, price
            elif cur_side:
                pnl = (price - cur_entry) / cur_entry * 100 * (1 if cur_side == "long" else -1)
                print(f"  {now} {sym:12} держим {cur_side:5} {why:16} PnL {pnl:+.2f}%")

            # состояние позиции для дашборда
            if cur_side:
                pnl = (price - cur_entry) / cur_entry * 100 * (1 if cur_side == "long" else -1)
                positions.append({"sym": short, "side": cur_side, "entry": round(cur_entry, 2),
                                  "price": round(price, 2), "pnl_pct": round(pnl, 2), "why": why})
        except Exception as e:
            print(f"  {now} {sym:12} ⚠️ {type(e).__name__}: {str(e)[:45]}")
    return traded, positions


def main():
    if not fb.has_keys():
        print("⚠️ Нет ключей фьючерсного демо (.env: FUTURES_KEY/FUTURES_SECRET).")
        return
    ex = fb.get_futures_exchange()
    bal = ex.fetch_balance()["total"].get("USDT", 0)
    print(f"🔴🟢 ЖИВОЙ ЛОНГ/ШОРТ · 5m · ${NOTIONAL_USD} · плечо {LEVERAGE}x · стоп {STOP_PCT*100:.0f}% · баланс {bal:.2f} USDT")
    print(f"Проверка каждые {CHECK_SEC} сек · дашборд обновляется при сделке и каждые {SYNC_EVERY} мин.")
    print("-" * 64)

    once = "--once" in sys.argv
    n = 0
    while True:
        try:
            traded, positions = tick(ex)
            publish(positions)
            if traded or n % SYNC_EVERY == 0:
                sync_site()
        except Exception as e:
            print(f"  ⚠️ цикл: {str(e)[:60]}")
        n += 1
        if once:
            break
        print("-" * 64)
        time.sleep(CHECK_SEC)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️ Остановлено.")
