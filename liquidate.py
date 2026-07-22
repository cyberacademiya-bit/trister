# -*- coding: utf-8 -*-
"""
РАСПРОДАЖА — закрывает ВСЕ позиции на ВСЕХ демо-счетах (уходим в кэш/USDT).
Только демо. Запуск с Мака (Binance тут доступен):

    python liquidate.py
"""
import os
from datetime import datetime, timezone, timedelta

BISHKEK = timezone(timedelta(hours=6))
STABLES = {"USDT", "USDC", "BUSD", "USD1", "FDUSD", "TUSD"}


def _geoblock(e):
    s = str(e).lower()
    return "451" in s or "restricted location" in s or "eligibility" in s


# ── 1. Binance Spot: продаём все монеты в USDT ──
def liquidate_spot():
    print("═══ Binance Spot ═══")
    try:
        import broker
        ex = broker.get_exchange()
        bal = {c: a for c, a in ex.fetch_balance()["total"].items() if a and a > 0}
        sold = 0
        for coin, amt in bal.items():
            if coin in STABLES:
                continue
            sym = f"{coin}/USDT"
            try:
                px = ex.fetch_ticker(sym)["last"]
                if amt * px < 1:        # пыль (< $1) — пропускаем
                    continue
                amount = float(ex.amount_to_precision(sym, amt))
                ex.create_market_sell_order(sym, amount)
                print(f"  ✅ Продал {amount} {coin}  (~${amt*px:.2f})")
                sold += 1
            except Exception as e:
                print(f"  ⚠️ {coin}: {str(e)[:50]}")
        print(f"  Итого продано позиций: {sold}" if sold else "  Нечего продавать (уже в USDT).")
    except Exception as e:
        print("  ⏭️ Binance недоступен (гео-блок), запусти с Мака." if _geoblock(e) else f"  ⚠️ {str(e)[:60]}")


# ── 2. Binance Futures: закрываем все позиции ──
def liquidate_futures():
    print("═══ Binance Futures ═══")
    try:
        import futures_broker as fb
        ex = fb.get_futures_exchange()
        closed = 0
        for p in ex.fetch_positions():
            amt = abs(float(p.get("contracts") or 0))
            if amt <= 0:
                continue
            sym, side = p["symbol"], p.get("side")
            try:
                ex.cancel_all_orders(sym)
            except Exception:
                pass
            try:
                if side == "long":
                    ex.create_market_sell_order(sym, amt, {"reduceOnly": True})
                else:
                    ex.create_market_buy_order(sym, amt, {"reduceOnly": True})
                print(f"  ✅ Закрыл {side} {sym} ({amt})")
                closed += 1
            except Exception as e:
                print(f"  ⚠️ {sym}: {str(e)[:50]}")
        print(f"  Итого закрыто позиций: {closed}" if closed else "  Открытых позиций нет.")
    except Exception as e:
        print("  ⏭️ Binance недоступен (гео-блок), запусти с Мака." if _geoblock(e) else f"  ⚠️ {str(e)[:60]}")


# ── 3. Alpaca: закрываем все акции ──
def liquidate_alpaca():
    print("═══ Alpaca (акции) ═══")
    try:
        from dotenv import load_dotenv
        load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
        key, secret = os.getenv("ALPACA_KEY"), os.getenv("ALPACA_SECRET")
        if not key:
            print("  ⚠️ нет ключей Alpaca"); return
        from alpaca.trading.client import TradingClient
        client = TradingClient(key, secret, paper=True)
        positions = client.get_all_positions()
        if not positions:
            print("  Позиций нет (всё в кэше).")
            return
        client.close_all_positions(cancel_orders=True)
        print(f"  ✅ Отправлен приказ закрыть {len(positions)} позиций: " + ", ".join(p.symbol for p in positions))
        print("  ⏳ Если биржа США закрыта — исполнится на открытии.")
    except Exception as e:
        print(f"  ⚠️ {str(e)[:60]}")


# ── 4. Локальный симулятор: продаём всё в кэш ──
def liquidate_local():
    print("═══ Локальный симулятор ═══")
    try:
        import paper
        import yfinance as yf
        acc = paper.load()
        syms = list(acc["positions"].keys())
        if not syms:
            print("  Позиций нет (всё в кэше).")
            return
        now = datetime.now(BISHKEK).strftime("%Y-%m-%d %H:%M")
        raw = yf.download(syms, period="5d", progress=False, auto_adjust=True, group_by="ticker")
        for s in syms:
            try:
                px = float(raw[s]["Close"].dropna().iloc[-1]) if len(syms) > 1 else float(raw["Close"].dropna().iloc[-1])
            except Exception:
                px = 0
            if paper.sell(acc, s, px, now):
                print(f"  ✅ Продал {s}  (${px:.2f})")
        paper.save(acc)
        print(f"  Кэш после распродажи: ${acc['cash']:,.2f}")
    except Exception as e:
        print(f"  ⚠️ {str(e)[:60]}")


if __name__ == "__main__":
    print("🧹 РАСПРОДАЖА ВСЕХ ДЕМО-СЧЕТОВ (уходим в кэш)\n")
    liquidate_spot()
    liquidate_futures()
    liquidate_alpaca()
    liquidate_local()
    print("\n✅ Готово. Обнови дашборд: python gather_data.py")
