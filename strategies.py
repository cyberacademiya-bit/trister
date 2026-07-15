# -*- coding: utf-8 -*-
"""
РЕЕСТР ВСЕХ СТРАТЕГИЙ бота «Тристер».
Каждая стратегия смотрит на данные и выдаёт позицию: 1=бык(лонг), 0=кэш, -1=медведь(шорт).
Бот берёт активную стратегию из config.STRATEGY.

Что показали наши бэктесты на золоте 2008-2026 (для честного выбора):
  trend    — 🏆 лучший (Sharpe 0.55, уворачивается от крахов)
  buyhold  — просто держать (высокий доход, но просадка −44%)
  cot      — тренд + COT Уильямса (безопаснее, но доход ниже)
  sma      — пересечение средних (проигрывает)
  candles  — свечи + индикаторы (в тесте УБЫТОЧНА, но по запросу оставлена)
"""
import numpy as np
import pandas as pd
from ta.momentum import RSIIndicator
from ta.trend import MACD, SMAIndicator


def add_indicators(df, cot_index=None):
    """Считает все индикаторы и свечные паттерны на дневных свечах."""
    df = df.copy()
    o, h, l, c = df["open"], df["high"], df["low"], df["close"]
    df["ma50"] = c.rolling(50).mean()
    df["ma200"] = c.rolling(200).mean()
    df["sma_fast"] = c.rolling(20).mean()
    df["sma_slow"] = c.rolling(50).mean()
    df["rsi"] = RSIIndicator(c, window=14).rsi()
    df["macd_diff"] = MACD(c).macd_diff()
    # свечные паттерны
    body = (c - o).abs()
    upsh = h - df[["open", "close"]].max(axis=1)
    losh = df[["open", "close"]].min(axis=1) - l
    green, red = (c > o), (c < o)
    pg, pr = green.shift(1).fillna(False), red.shift(1).fillna(False)
    p_open, p_close = o.shift(1), c.shift(1)
    df["hammer"] = (losh > 2 * body) & (upsh < body) & (body > 0)
    df["star"] = (upsh > 2 * body) & (losh < body) & (body > 0)
    df["bull_engulf"] = (pr & green & (o < p_close) & (c > p_open)).fillna(False)
    df["bear_engulf"] = (pg & red & (o > p_close) & (c < p_open)).fillna(False)
    if cot_index is not None:
        df["comm_idx"] = cot_index
    return df


def _candle_score(df):
    s = pd.Series(0.0, index=df.index)
    s += df["hammer"].astype(int) + df["bull_engulf"].astype(int)
    s -= df["star"].astype(int) + df["bear_engulf"].astype(int)
    s += (df["rsi"] < 30).astype(int) - (df["rsi"] > 70).astype(int)
    s += (df["macd_diff"] > 0).astype(int) - (df["macd_diff"] < 0).astype(int)
    s += (df["close"] > df["sma_slow"]).astype(int) - (df["close"] < df["sma_slow"]).astype(int)
    return s


# ── стратегии: df → позиция (Series из -1/0/1) ──
def s_buyhold(df):
    return pd.Series(1.0, index=df.index)

def s_sma(df):
    return (df["sma_fast"] > df["sma_slow"]).astype(float)

def s_trend(df):
    return ((df["ma50"] > df["ma200"]) & (df["close"] > df["ma200"])).astype(float)

def s_cot(df):
    base = (df["ma50"] > df["ma200"]) & (df["close"] > df["ma200"])
    if "comm_idx" in df.columns:
        base = base & (df["comm_idx"] >= 40)
    return base.astype(float)

def s_candles(df):
    sc = _candle_score(df)
    return pd.Series(np.select([sc >= 2, sc <= -2], [1.0, -1.0], 0.0), index=df.index)

def s_trend_ls(df):
    # Лонг/шорт по тренду — для фьючерсов (умеет шортить на падении)
    return pd.Series(np.where(df["ma50"] > df["ma200"], 1.0, -1.0), index=df.index)


REGISTRY = {
    "buyhold": ("📊 Купи и держи",            s_buyhold, "лонг всегда"),
    "sma":     ("📈 SMA 20/50",               s_sma,     "лонг/кэш"),
    "trend":   ("🏆 Тренд MA50/200 (лучший)", s_trend,   "лонг/кэш"),
    "cot":     ("🧠 Тренд + COT Уильямса",    s_cot,     "лонг/кэш"),
    "candles": ("🕯️ Свечи + индикаторы",      s_candles, "лонг/шорт"),
    "trend_ls": ("↕️ Тренд лонг/шорт (фьючерсы)", s_trend_ls, "лонг/шорт"),
}

_LABEL = {1: "🟢 БЫК (лонг)", 0: "⚪ вне рынка (кэш)", -1: "🔴 МЕДВЕДЬ (шорт)"}


def signal_now(name, ohlc_df, cot_index=None):
    """Текущий сигнал стратегии. Возвращает (позиция -1/0/1, текст, строка данных)."""
    title, fn, kind = REGISTRY[name]
    df = add_indicators(ohlc_df.sort_values("dt"), cot_index)
    pos = int(fn(df).iloc[-1])
    return pos, _LABEL.get(pos, str(pos)), df.iloc[-1]
