# -*- coding: utf-8 -*-
"""
Журнал сделок и решений бота — пишет в trades.csv.
Чтобы потом честно посчитать, как бот отторговал.
"""
import csv
import os
from datetime import datetime

JOURNAL_FILE = os.path.join(os.path.dirname(__file__), "trades.csv")
_HEADER = ["time", "action", "signal", "price", "amount_btc", "cost_usdt", "note"]


def log(action, signal=None, price=None, amount_btc=None, cost_usdt=None, note=""):
    new = not os.path.exists(JOURNAL_FILE)
    with open(JOURNAL_FILE, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if new:
            w.writerow(_HEADER)
        w.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            action, signal, price, amount_btc, cost_usdt, note,
        ])
