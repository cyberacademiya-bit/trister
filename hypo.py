# -*- coding: utf-8 -*-
"""
БОЛЬШОЙ ТЕСТ ГИПОТЕЗ — 9 стратегий × 11 рынков × out-of-sample.
Честно проверяет, какая логика реально работает (и не переобучена).
Запуск: python hypo.py  → отчёт + Данные/hypothesis_results.csv
"""
import numpy as np
import pandas as pd
import yfinance as yf

import strategies as S

MARKETS = {
    "Золото": "GC=F", "Серебро": "SI=F", "Нефть": "CL=F", "Медь": "HG=F",
    "Bitcoin": "BTC-USD", "Ethereum": "ETH-USD", "S&P500": "SPY", "Nasdaq": "QQQ",
    "Apple": "AAPL", "Nvidia": "NVDA", "Облигации": "TLT",
}
FEE, PPY = 0.0005, 252


def strat_positions(df):
    o = {}
    o["buyhold"] = pd.Series(1.0, index=df.index)
    o["trend"] = S.s_trend(df)
    o["trend_ls"] = S.s_trend_ls(df)
    o["sma_20_50"] = (df["sma_fast"] > df["sma_slow"]).astype(float)
    ma10, ma30 = df["close"].rolling(10).mean(), df["close"].rolling(30).mean()
    o["sma_10_30"] = (ma10 > ma30).astype(float)
    o["candles"] = S.s_candles(df)
    rsi_sig = np.where(df["rsi"] < 35, 1.0, np.where(df["rsi"] > 65, 0.0, np.nan))
    o["rsi_meanrev"] = pd.Series(rsi_sig, index=df.index).ffill().fillna(0)
    o["macd"] = (df["macd_diff"] > 0).astype(float)
    high20 = df["close"].rolling(20).max()
    o["breakout20"] = (df["close"] >= high20 * 0.999).astype(float)
    return o


def bt(df, pos, mask=None):
    p = pos.shift(1).fillna(0)
    ret = df["close"].pct_change().fillna(0)
    if mask is not None:
        p, ret = p[mask], ret[mask]
    strat = p * ret - p.diff().abs().fillna(0) * FEE
    eq = (1 + strat).cumprod()
    yrs = max(len(ret) / PPY, 0.1)
    return dict(cagr=eq.iloc[-1] ** (1 / yrs) - 1, dd=float((eq / eq.cummax() - 1).min()),
                sharpe=float(strat.mean() / strat.std() * np.sqrt(PPY)) if strat.std() else 0.0)


print("Скачиваю историю 11 рынков (с 2015)...")
raw = yf.download(list(MARKETS.values()), start="2015-01-01", progress=False, auto_adjust=True, group_by="ticker")

rows = []
for mname, tk in MARKETS.items():
    try:
        d = raw[tk].dropna().reset_index()
        d.columns = [str(c).lower() for c in d.columns]
        d = d.rename(columns={"date": "dt"})
        df = S.add_indicators(d[["dt", "open", "high", "low", "close"]])
        if len(df) < 260:
            continue
        half = df.index <= df.index[len(df) // 2]
        for sname, pos in strat_positions(df).items():
            full = bt(df, pos)
            oos = bt(df, pos, ~half)          # 2-я половина = out-of-sample
            ins = bt(df, pos, half)           # 1-я половина = in-sample
            bh = bt(df, strat_positions(df)["buyhold"])["cagr"]
            rows.append({"рынок": mname, "стратегия": sname,
                         "CAGR": full["cagr"], "просадка": full["dd"], "Sharpe": full["sharpe"],
                         "IS_CAGR": ins["cagr"], "OOS_CAGR": oos["cagr"],
                         "обыграл_BH": full["cagr"] > bh})
    except Exception as e:
        print(f"  ✗ {mname}: {type(e).__name__}")

res = pd.DataFrame(rows)
res.to_csv("Данные/hypothesis_results.csv", index=False)

# ── АГРЕГАТ ПО СТРАТЕГИЯМ (усреднение по рынкам) ──
agg = res.groupby("стратегия").agg(
    ср_Sharpe=("Sharpe", "mean"),
    ср_CAGR=("CAGR", "mean"),
    ср_просадка=("просадка", "mean"),
    обыграл_BH=("обыграл_BH", "mean"),
    OOS_плюс=("OOS_CAGR", lambda x: (x > 0).mean()),          # доля рынков с плюсом на OOS
    устойчивость=("OOS_CAGR", lambda x: 0),                    # заполним ниже
).round(3)
# устойчивость: и IS, и OOS положительны (не переобучено)
stab = res.assign(ok=(res.IS_CAGR > 0) & (res.OOS_CAGR > 0)).groupby("стратегия")["ok"].mean()
agg["устойчивость"] = stab.round(3)
agg = agg.sort_values("ср_Sharpe", ascending=False)

print("\n" + "=" * 84)
print("  РЕЙТИНГ ГИПОТЕЗ (усреднено по 11 рынкам · 2015-2026 · с out-of-sample)")
print("=" * 84)
print(f"{'Стратегия':14} {'ср.Sharpe':>10} {'ср.CAGR':>9} {'ср.просад':>10} {'бьёт B&H':>9} {'OOS+':>6} {'устойч.':>8}")
print("-" * 84)
for name, r in agg.iterrows():
    print(f"{name:14} {r['ср_Sharpe']:10.2f} {r['ср_CAGR']*100:+8.1f}% {r['ср_просадка']*100:9.1f}% "
          f"{r['обыграл_BH']*100:7.0f}% {r['OOS_плюс']*100:5.0f}% {r['устойчивость']*100:7.0f}%")
print("-" * 84)
best = agg.index[0]
print(f"\n🏆 Лучшая по риск/доходности: '{best}' (ср.Sharpe {agg.iloc[0]['ср_Sharpe']:.2f})")
print(f"📊 Всего протестировано: {len(res)} комбинаций (стратегия×рынок)")
print(f"💾 Полная таблица: Данные/hypothesis_results.csv")
