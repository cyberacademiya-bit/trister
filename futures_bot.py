# -*- coding: utf-8 -*-
"""
ФЬЮЧЕРСНЫЙ бот — ЛОНГ + ШОРТ + стоп-лосс на Binance Futures Testnet (демо).
Наконец умеет зарабатывать и на падении (шорт).

  python futures_bot.py --compare  → сигналы (работает и без ключей)
  python futures_bot.py            → торговать на фьючерсном демо
"""
import sys

import data
import strategies
import futures_broker as fb
import journal

FUTURES_UNIVERSE = ["BTC/USDT", "ETH/USDT"]   # перпетуалы
STRATEGY = "trend_ls"    # лонг/шорт-стратегия (шортит на падении)
LEVERAGE = 2             # плечо (небольшое — безопаснее)
NOTIONAL_USD = 300       # размер позиции (номинал, демо). «По-крупному» — $300 на сделку
STOP_PCT = 0.03          # стоп-лосс 3%


def signals():
    out = {}
    for sym in FUTURES_UNIVERSE:
        ohlc = data.fetch_ohlcv(symbol=sym, timeframe="1d", days=400, use_cache=False)
        pos, txt, _ = strategies.signal_now(STRATEGY, ohlc)
        out[sym] = (pos, txt)
    return out


def get_position(ex, symbol):
    for p in ex.fetch_positions([symbol]):
        amt = abs(float(p.get("contracts") or 0))
        if amt > 0:
            return p.get("side"), amt, float(p.get("entryPrice") or 0)  # side, размер, вход
    return None, 0.0, 0.0


def open_pos(ex, symbol, direction, price):
    try:
        ex.set_leverage(LEVERAGE, symbol)
    except Exception:
        pass
    amount = float(ex.amount_to_precision(symbol, NOTIONAL_USD / price))
    if direction == "long":
        ex.create_market_buy_order(symbol, amount)
    else:
        ex.create_market_sell_order(symbol, amount)


def close_pos(ex, symbol, side, amount):
    try:
        ex.cancel_all_orders(symbol)
    except Exception:
        pass
    if side == "long":
        ex.create_market_sell_order(symbol, amount, {"reduceOnly": True})
    else:
        ex.create_market_buy_order(symbol, amount, {"reduceOnly": True})


SETUP = """
⚠️  Нет ключей фьючерсного демо. Как получить (2 минуты):
  1. Зайди на  https://testnet.binancefuture.com   (именно future!)
  2. Log In / Register (Google / GitHub / почта)
  3. Прокрути страницу в САМЫЙ НИЗ → блок «API Key»
  4. Скопируй API Key и Secret Key
  5. Кинь мне — впишу в .env как FUTURES_KEY / FUTURES_SECRET, и бот заторгует.
"""


def main():
    sig = signals()

    if not fb.has_keys():
        print(SETUP)
        print(f"Сигналы фьючерсов (стратегия '{STRATEGY}', лонг/шорт):")
        print("-" * 44)
        for sym, (pos, txt) in sig.items():
            print(f"  {sym:12} {txt}")
        return

    ex = fb.get_futures_exchange()
    bal = ex.fetch_balance()
    usdt = bal["total"].get("USDT", 0)
    print(f"Фьючерсный демо · баланс {usdt:.2f} USDT · плечо {LEVERAGE}x · стоп {STOP_PCT*100:.0f}%")
    print("-" * 56)

    compare = "--compare" in sys.argv
    for sym, (pos, txt) in sig.items():
        want = "long" if pos == 1 else "short" if pos == -1 else "flat"
        cur_side, cur_amt, entry = get_position(ex, sym)
        price = ex.fetch_ticker(sym)["last"]
        if compare:
            print(f"  {sym:12} {txt:20} позиция: {cur_side or 'нет'}")
            continue
        try:
            # 1) ПРОГРАММНЫЙ СТОП-ЛОСС: закрываем, если убыток превысил порог
            if cur_side and entry:
                loss = (price - entry) / entry if cur_side == "short" else (entry - price) / entry
                if loss >= STOP_PCT:
                    close_pos(ex, sym, cur_side, cur_amt)
                    print(f"  {sym:12} 🛑 СТОП-ЛОСС −{loss*100:.1f}% — закрыл {cur_side}")
                    journal.log("СТОП-ЛОСС", signal=f"{sym} {cur_side}", price=price,
                                note=f"убыток −{loss*100:.1f}% — продал при риске")
                    cur_side = None

            # 2) ЛОГИКА СТРАТЕГИИ
            if want == "flat":
                if cur_side:
                    close_pos(ex, sym, cur_side, cur_amt); print(f"  {sym:12} {txt:20} ✅ ЗАКРЫЛ")
                    journal.log("ЗАКРЫЛ", signal=f"{sym} {cur_side}", price=price, note=txt)
                else:
                    print(f"  {sym:12} {txt:20} вне рынка")
            elif want != cur_side:
                if cur_side:
                    close_pos(ex, sym, cur_side, cur_amt)
                open_pos(ex, sym, want, price)
                arrow = "🟢 ЛОНГ" if want == "long" else "🔴 ШОРТ"
                print(f"  {sym:12} {txt:20} ✅ ОТКРЫЛ {arrow}")
                journal.log(f"ОТКРЫЛ {want}", signal=f"{sym} {txt}", price=price,
                            cost_usdt=NOTIONAL_USD, note=f"плечо {LEVERAGE}x, стоп {STOP_PCT*100:.0f}%")
            elif cur_side:
                print(f"  {sym:12} {txt:20} держим {cur_side}")
        except Exception as e:
            print(f"  {sym:12} ⚠️ {type(e).__name__}: {str(e)[:50]}")


def _is_geoblock(err):
    s = str(err).lower()
    return "451" in s or "restricted location" in s or "eligibility" in s


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        if _is_geoblock(e):
            print("ℹ️  Binance Futures недоступен с этого сервера (гео-блок 451). "
                  "Фьючерсы (лонг/шорт+стоп) торгуются с Мака. Пропускаю.")
            sys.exit(0)   # не роняем прогон — это ограничение Binance, а не ошибка бота
        raise
