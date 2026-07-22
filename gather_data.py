# -*- coding: utf-8 -*-
"""Собирает данные ВСЕХ демо-счетов в один JSON для дашборда."""
import json
import os
from datetime import datetime, timezone, timedelta

import pandas as pd

BISHKEK = timezone(timedelta(hours=6))   # время Кыргызстана (GMT+6)


CACHE_FILE = os.path.join("Данные", "binance_cache.json")


def load_cache():
    try:
        return json.load(open(CACHE_FILE, encoding="utf-8"))
    except Exception:
        return {}


_cache = load_cache()


def acc_ok(name, kind, total, start, positions):
    """Успех (запуск с Мака): запоминаем баланс в кэш, чтобы показывать его и с облака."""
    _cache[name] = {"total": total, "positions": positions,
                    "time": datetime.now(BISHKEK).strftime("%Y-%m-%d %H:%M")}
    return {"name": name, "kind": kind, "total": total, "start": start,
            "positions": positions, "status": "ok"}


def acc_err(name, kind, start, e):
    """Аккуратный статус для упавшего счёта. Гео-блок Binance (451) — не ошибка бота, а
    ограничение Binance для облака. Если есть запомненный баланс с Мака — показываем его."""
    s = str(e).lower()
    geo = "451" in s or "restricted location" in s or "eligibility" in s
    cached = _cache.get(name)
    if geo and cached:
        return {"name": name, "kind": kind, "total": cached["total"], "start": start,
                "positions": cached.get("positions", []), "status": "offline",
                "error": f"Binance блокирует облако. Последний баланс с Мака: {cached['time']}"}
    if geo:
        return {"name": name, "kind": kind, "status": "offline",
                "error": "Binance блокирует облако (гео-блок). Запусти с Мака, чтобы увидеть баланс."}
    return {"name": name, "kind": kind, "status": "error", "error": str(e)[:80]}


snap = {"generated": datetime.now(BISHKEK).strftime("%Y-%m-%d %H:%M") + " (Бишкек)",
        "accounts": [], "transactions": [], "hypotheses": [], "usage": {}}

# ── 1. Binance Spot ──
try:
    import broker
    ex = broker.get_exchange()
    bal = {c: a for c, a in ex.fetch_balance()["total"].items() if a and a > 0.0001}
    pos, total = [], 0.0
    for c, a in bal.items():
        v = a if c in ("USDT", "USDC", "BUSD", "USD1") else a * ex.fetch_ticker(f"{c}/USDT")["last"]
        if v > 0.01:
            pos.append({"asset": c, "amount": round(a, 6), "usd": round(v, 2)})
        total += v
    snap["accounts"].append(acc_ok("Binance Spot", "Крипта + Золото", round(total, 2), 10000,
                                   sorted(pos, key=lambda x: -x["usd"])))
except Exception as e:
    snap["accounts"].append(acc_err("Binance Spot", "Крипта + Золото", 10000, e))

# ── 2. Binance Futures ──
try:
    import futures_broker as fb
    ex = fb.get_futures_exchange()
    usdt = float(ex.fetch_balance()["total"].get("USDT", 0))
    pos = []
    for p in ex.fetch_positions(["BTC/USDT", "ETH/USDT"]):
        amt = abs(float(p.get("contracts") or 0))
        if amt > 0:
            pos.append({"asset": p["symbol"].split(":")[0], "side": p.get("side"),
                        "entry": round(float(p.get("entryPrice") or 0), 2),
                        "pnl": round(float(p.get("unrealizedPnl") or 0), 3)})
    snap["accounts"].append(acc_ok("Binance Futures", "Фьючерсы (лонг/шорт)", round(usdt, 2), 5000, pos))
except Exception as e:
    snap["accounts"].append(acc_err("Binance Futures", "Фьючерсы (лонг/шорт)", 5000, e))

# ── 3. Alpaca (акции) ──
try:
    from dotenv import load_dotenv
    load_dotenv(".env")
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import GetOrdersRequest
    from alpaca.trading.enums import QueryOrderStatus
    c = TradingClient(os.getenv("ALPACA_KEY"), os.getenv("ALPACA_SECRET"), paper=True)
    acct = c.get_account()
    pos = [{"asset": p.symbol, "amount": float(p.qty), "usd": round(float(p.market_value), 2)}
           for p in c.get_all_positions()]
    snap["accounts"].append({"name": "Alpaca", "kind": "Акции США", "total": round(float(acct.portfolio_value), 2),
                             "start": 100000, "positions": pos, "status": "ok"})
    for o in c.get_orders(GetOrdersRequest(status=QueryOrderStatus.ALL, limit=30)):
        st = str(o.status).split(".")[-1].lower()
        snap["transactions"].append({"time": str(o.submitted_at)[:16], "account": "Alpaca",
                                     "action": str(o.side).split(".")[-1].upper(), "asset": o.symbol,
                                     "amount": f"${o.notional or o.qty}", "status": st})
except Exception as e:
    snap["accounts"].append({"name": "Alpaca", "kind": "Акции США", "status": "error", "error": str(e)[:80]})

# ── 4. Локальный ──
try:
    acc = json.load(open("Данные/paper_account.json", encoding="utf-8"))
    total = acc["cash"] + sum(p["cost"] for p in acc["positions"].values())
    pos = [{"asset": s, "amount": round(p["qty"], 6), "usd": round(p["cost"], 2)} for s, p in acc["positions"].items()]
    snap["accounts"].append({"name": "Локальный", "kind": "Все рынки (виртуально)", "total": round(total, 2),
                             "start": acc.get("start", 10000), "positions": pos, "status": "ok"})
    for h in acc.get("history", [])[-15:]:
        snap["transactions"].append({"time": h.get("t"), "account": "Локальный", "action": h["action"],
                                    "asset": h["symbol"], "amount": f"${h['usd']}", "status": "filled"})
except Exception as e:
    snap["accounts"].append({"name": "Локальный", "kind": "Все рынки", "status": "error", "error": str(e)[:80]})

# ── Транзакции из журнала бота (trades.csv) ──
try:
    t = pd.read_csv("trades.csv")
    for _, r in t.tail(20).iterrows():
        snap["transactions"].append({"time": str(r["time"]), "account": "Binance Spot", "action": r["action"],
                                    "asset": "PAXG/BTC", "amount": f"${r.get('cost_usdt','')}", "status": "filled"})
except Exception:
    pass

# ── Гипотезы (топ стратегий) ──
try:
    res = pd.read_csv("Данные/hypothesis_results.csv")
    agg = res.groupby("стратегия").agg(sharpe=("Sharpe", "mean"), cagr=("CAGR", "mean"),
                                       dd=("просадка", "mean")).sort_values("sharpe", ascending=False)
    for name, r in agg.iterrows():
        snap["hypotheses"].append({"name": name, "sharpe": round(r["sharpe"], 2),
                                  "cagr": round(r["cagr"] * 100, 1), "dd": round(r["dd"] * 100, 1)})
except Exception:
    pass

# ── Битва стратегий (турнир) ──
try:
    snap["battle"] = json.load(open("Данные/strategy_battle.json", encoding="utf-8"))
except Exception:
    snap["battle"] = None

# ── Живая торговля фьючерсами (5m лонг/шорт, пишет futures_live.py) ──
try:
    snap["live"] = json.load(open("Данные/live_futures.json", encoding="utf-8"))
except Exception:
    snap["live"] = None

# ── Usage: сводка по транзакциям ──
tx = snap["transactions"]
snap["usage"] = {"total": len(tx),
                 "filled": sum(1 for x in tx if x["status"] in ("filled", "closed")),
                 "pending": sum(1 for x in tx if x["status"] in ("new", "accepted", "pending_new")),
                 "failed": sum(1 for x in tx if x["status"] in ("rejected", "canceled", "expired"))}
# В сумму входят онлайн-счета + офлайн с запомненным балансом (у чистых ошибок 'total' нет → 0)
snap["total_value"] = round(sum(a.get("total", 0) for a in snap["accounts"]), 2)

# Сохраняем кэш балансов Binance (пополняется при запуске с Мака)
try:
    os.makedirs("Данные", exist_ok=True)
    json.dump(_cache, open(CACHE_FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
except Exception:
    pass

json.dump(snap, open("Данные/dashboard_data.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
# копия для сайта (Vercel читает её и авто-обновляется)
os.makedirs("site", exist_ok=True)
json.dump(snap, open("site/dashboard_data.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)
print("✅ Собрано. Счетов:", len(snap["accounts"]), "| транзакций:", len(tx))
print("Общая стоимость всех демо:", f"${snap['total_value']:,.2f}")
for a in snap["accounts"]:
    print(f"  {a['name']:18} {a.get('status')}: ${a.get('total','—')}")
