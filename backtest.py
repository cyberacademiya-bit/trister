# -*- coding: utf-8 -*-
"""
Бэктест-движок: прогоняет стратегию по историческим данным и считает,
сколько бы мы заработали/потеряли. С учётом комиссий и БЕЗ заглядывания в будущее.

Главное сравнение — не «плюс или минус», а «обыграли ли мы buy & hold»
(просто купить и держать). Стратегия, которая хуже «купил и забыл», — бесполезна.
"""
import numpy as np

import config

# сколько периодов данного таймфрейма в году (для годового Sharpe)
_PERIODS_PER_YEAR = {
    "1m": 525600, "5m": 105120, "15m": 35040, "30m": 17520,
    "1h": 8760, "2h": 4380, "4h": 2190, "6h": 1460, "12h": 730, "1d": 365,
}


def run(df, initial=None, fee=None):
    initial = initial if initial is not None else config.INITIAL_CAPITAL
    fee = fee if fee is not None else config.FEE
    df = df.copy()

    # доходность рынка по свече и доходность стратегии (позиция * рынок)
    df["returns"] = df["close"].pct_change().fillna(0)
    df["strat_returns"] = df["position"] * df["returns"]

    # комиссия в момент смены позиции (вход/выход)
    df["trade"] = df["position"].diff().abs().fillna(0)
    df["strat_returns"] -= df["trade"] * fee

    # кривые капитала: наша стратегия vs «купил и держи»
    df["equity"] = initial * (1 + df["strat_returns"]).cumprod()
    df["buy_hold"] = initial * (1 + df["returns"]).cumprod()

    return df, _metrics(df, initial, fee)


def _metrics(df, initial, fee):
    eq = df["equity"]
    final = eq.iloc[-1]
    bh_final = df["buy_hold"].iloc[-1]

    # число полных входов в позицию
    entries = int((df["position"].diff() == 1).sum())

    # макс. просадка (насколько глубоко проседал капитал от пика)
    drawdown = eq / eq.cummax() - 1
    max_dd = float(drawdown.min())

    # годовой коэффициент Шарпа (доходность на единицу риска)
    r = df["strat_returns"]
    ppy = _PERIODS_PER_YEAR.get(config.TIMEFRAME, 8760)
    sharpe = float(r.mean() / r.std() * np.sqrt(ppy)) if r.std() > 0 else 0.0

    # winrate по сделкам
    pnls = _trade_pnls(df)
    winrate = float(np.mean([p > 0 for p in pnls])) if pnls else 0.0

    return {
        "final_equity": float(final),
        "total_return": float(final / initial - 1),
        "buy_hold_return": float(bh_final / initial - 1),
        "trades": entries,
        "winrate": winrate,
        "max_drawdown": max_dd,
        "sharpe": sharpe,
    }


def _trade_pnls(df):
    """Доходность каждой отдельной сделки (для winrate). Приближённо, по close."""
    pnls = []
    in_pos = False
    entry = None
    closes = df["close"].values
    pos = df["position"].values
    for i in range(len(df)):
        if pos[i] == 1 and not in_pos:
            in_pos, entry = True, closes[i]
        elif pos[i] == 0 and in_pos:
            in_pos = False
            pnls.append(closes[i] / entry - 1)
    if in_pos:                       # позиция открыта на конце истории — закрываем по последней цене
        pnls.append(closes[-1] / entry - 1)
    return pnls
