# -*- coding: utf-8 -*-
"""
ТУРНИР СТРАТЕГИЙ — каждая стратегия торгует свой портфель по ВСЕМ рынкам.
Равный вес по 16 инструментам, лонг/шорт, антизаглядывание. Кто впереди — тот и лучший.
Стейтлесс: каждый запуск пересчитывает кривые из истории (для дневного крона).
Запуск: python multi_strategy.py → Данные/strategy_battle.json
"""
import json
import os

import numpy as np
import pandas as pd
import yfinance as yf

import strategies as S

MARKETS = {
    "Золото": "GC=F", "Серебро": "SI=F", "Платина": "PL=F", "Медь": "HG=F", "Нефть": "CL=F",
    "Apple": "AAPL", "Microsoft": "MSFT", "Nvidia": "NVDA", "Amazon": "AMZN", "Google": "GOOGL",
    "S&P500": "SPY", "Nasdaq": "QQQ", "Bitcoin": "BTC-USD", "Ethereum": "ETH-USD",
    "Tesla": "TSLA", "Meta": "META",
}
STRATS = ["buyhold", "sma", "trend", "cot", "candles", "trend_ls"]
FEE, START = 0.0005, 10000.0

print(f"Скачиваю {len(MARKETS)} рынков (с 2024)...")
raw = yf.download(list(MARKETS.values()), start="2024-01-01", progress=False, auto_adjust=True, group_by="ticker")

data = {}
for m, tk in MARKETS.items():
    try:
        d = raw[tk].dropna().reset_index()
        d.columns = [str(c).lower() for c in d.columns]
        d = d.rename(columns={"date": "dt"})
        df = S.add_indicators(d[["dt", "open", "high", "low", "close"]]).set_index("dt")
        if len(df) > 210:
            data[m] = df
    except Exception:
        pass

master = sorted(set().union(*[df.index for df in data.values()]))
closes = pd.DataFrame({m: data[m]["close"] for m in data}).reindex(master).ffill()
rets = closes.pct_change().fillna(0)

results = []
for st in STRATS:
    fn = S.REGISTRY[st][1]
    pos = pd.DataFrame({m: fn(data[m]).reindex(master).ffill().fillna(0) for m in data})
    port = (pos.shift(1).fillna(0) * rets).mean(axis=1)
    turnover = pos.diff().abs().fillna(0).mean(axis=1)
    net = port - turnover * FEE
    eq = START * (1 + net).cumprod()
    final = float(eq.iloc[-1])
    curve = [round(x, 1) for x in eq.iloc[::max(1, len(eq) // 24)].tolist()][-24:]  # ~24 точки
    longs = int((pos.iloc[-1] == 1).sum())
    shorts = int((pos.iloc[-1] == -1).sum())
    results.append({"name": st, "title": S.REGISTRY[st][0], "equity": round(final, 2),
                    "ret": round(final / START - 1, 4) * 100, "longs": longs, "shorts": shorts,
                    "curve": curve})

results.sort(key=lambda x: -x["equity"])
out = {"period": f"{str(master[0])[:10]} → {str(master[-1])[:10]}", "markets": len(data), "strategies": results}
os.makedirs("Данные", exist_ok=True)
json.dump(out, open("Данные/strategy_battle.json", "w", encoding="utf-8"), ensure_ascii=False, indent=2)

print("\n" + "=" * 62)
print(f"  🏁 ТУРНИР СТРАТЕГИЙ · {len(data)} рынков · {out['period']}")
print("=" * 62)
print(f"{'#':>2} {'Стратегия':16} {'Портфель':>12} {'Доход':>9} {'позиции':>12}")
print("-" * 62)
for i, r in enumerate(results, 1):
    medal = "🥇" if i == 1 else "🥈" if i == 2 else "🥉" if i == 3 else "  "
    print(f"{medal}{i:>1} {r['name']:16} ${r['equity']:>10,.0f} {r['ret']:>+7.1f}% "
          f"{r['longs']}L/{r['shorts']}S")
print("-" * 62)
print(f"🏆 Победитель забега: {results[0]['name']} (${results[0]['equity']:,.0f})")
