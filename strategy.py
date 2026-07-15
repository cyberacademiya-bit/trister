# -*- coding: utf-8 -*-
"""
Стратегии = логика «когда мы в позиции, когда нет».
Каждая функция добавляет столбец `position`: 1 = в лонге, 0 = вне рынка.

ВАЖНО: сигнал сдвигаем на 1 свечу вперёд (.shift(1)).
Это защита от «заглядывания в будущее» — мы входим на СЛЕДУЮЩЕЙ свече
после того, как сигнал появился, а не на той же (которую в реале ещё не видели).
"""
import config


def sma_crossover(df, fast=None, slow=None):
    """Классика: быстрая SMA выше медленной → лонг, иначе → вне рынка."""
    fast = fast or config.FAST
    slow = slow or config.SLOW
    df = df.copy()

    df["sma_fast"] = df["close"].rolling(fast).mean()
    df["sma_slow"] = df["close"].rolling(slow).mean()

    df["signal"] = 0
    df.loc[df["sma_fast"] > df["sma_slow"], "signal"] = 1

    df["position"] = df["signal"].shift(1).fillna(0)   # без заглядывания в будущее
    return df
