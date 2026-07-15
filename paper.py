# -*- coding: utf-8 -*-
"""
ЛОКАЛЬНЫЙ демо-счёт (paper trading) — виртуальные деньги, настоящие цены.
Без брокера, без KYC, торгует любой инструмент. Состояние в Данные/paper_account.json.
"""
import json
import os

FILE = os.path.join(os.path.dirname(__file__), "Данные", "paper_account.json")
START_CASH = 10000.0


def load():
    if os.path.exists(FILE):
        return json.load(open(FILE, encoding="utf-8"))
    return {"cash": START_CASH, "start": START_CASH, "positions": {}, "history": []}


def save(acc):
    os.makedirs(os.path.dirname(FILE), exist_ok=True)
    json.dump(acc, open(FILE, "w", encoding="utf-8"), ensure_ascii=False, indent=2)


def buy(acc, symbol, usd, px, when):
    if usd <= 0 or acc["cash"] < usd or not px:
        return False
    qty = usd / px
    pos = acc["positions"].get(symbol, {"qty": 0.0, "cost": 0.0})
    pos["qty"] += qty
    pos["cost"] += usd
    acc["positions"][symbol] = pos
    acc["cash"] -= usd
    acc["history"].append({"t": when, "action": "BUY", "symbol": symbol, "usd": round(usd, 2), "px": px})
    return True


def sell(acc, symbol, px, when):
    pos = acc["positions"].get(symbol)
    if not pos or pos["qty"] <= 0 or not px:
        return False
    usd = pos["qty"] * px
    pnl = usd - pos["cost"]
    acc["cash"] += usd
    acc["history"].append({"t": when, "action": "SELL", "symbol": symbol,
                           "usd": round(usd, 2), "px": px, "pnl": round(pnl, 2)})
    del acc["positions"][symbol]
    return True


def value(acc, prices):
    v = acc["cash"]
    for s, pos in acc["positions"].items():
        v += pos["qty"] * prices.get(s, 0)
    return v
