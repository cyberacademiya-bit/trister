# -*- coding: utf-8 -*-
"""
Обновление данных для робота. Запуск:  python update_data.py
Тянет и сохраняет в папку Данные/:
  • COT по золоту (CFTC, еженедельно) + индекс Уильямса
  • Индекс страха и жадности (крипта)
  • FRED-макро (best-effort: цена золота, ставка, инфляция, доллар) — может отвалиться по таймауту
"""
import os, io, requests
import pandas as pd

HERE = os.path.dirname(__file__)
DST = os.path.join(HERE, "Данные")
os.makedirs(DST, exist_ok=True)
UA = {"User-Agent": "Mozilla/5.0"}
LOOKBACK = 26  # недель для индекса Уильямса (~полгода)


def update_gold_cot():
    """COT по золоту + индекс Уильямса (позиции коммерсантов = «умные деньги»)."""
    import cot_reports as cot
    frames = []
    for yr in (2024, 2025, 2026):
        try:
            frames.append(cot.cot_year(year=yr, cot_report_type="legacy_fut"))
        except Exception:
            pass
    allc = pd.concat(frames, ignore_index=True)
    junk = os.path.join(HERE, "annual.txt")
    if os.path.exists(junk):
        os.remove(junk)

    ncol = next(c for c in allc.columns if "Market_and_Exchange" in c or "Market and Exchange" in c)
    g = allc[allc[ncol].str.contains("COMMODITY EXCHANGE", na=False)].copy()
    g = g[g[ncol].str.contains("GOLD", case=False, na=False)]
    g.to_csv(os.path.join(DST, "gold_COT.csv"), index=False)

    dcol = next(c for c in g.columns if "yyyy-mm-dd" in c.lower())
    g["date"] = pd.to_datetime(g[dcol], errors="coerce")
    g = g.dropna(subset=["date"]).sort_values("date")
    L = next(c for c in g.columns if "Commercial Positions-Long" in c)
    S = next(c for c in g.columns if "Commercial Positions-Short" in c)
    g["comm_net"] = g[L].astype(float) - g[S].astype(float)
    mn = g["comm_net"].rolling(LOOKBACK).min()
    mx = g["comm_net"].rolling(LOOKBACK).max()
    g["williams_cot_index"] = 100 * (g["comm_net"] - mn) / (mx - mn)
    g[["date", L, S, "comm_net", "williams_cot_index"]].to_csv(
        os.path.join(DST, "gold_williams_cot_index.csv"), index=False)

    last = g.iloc[-1]
    idx = last["williams_cot_index"]
    sig = "БЫЧИЙ" if idx > 75 else "МЕДВЕЖИЙ" if idx < 25 else "нейтральный"
    print(f"  ✅ COT золото: {len(g)} недель, отчёт от {last['date'].date()}")
    print(f"     Индекс Уильямса (26 нед): {idx:.0f}% → {sig}")


def update_fear_greed():
    r = requests.get("https://api.alternative.me/fng/?limit=0&format=json", headers=UA, timeout=40)
    data = r.json()["data"]
    df = pd.DataFrame(data)
    df["date"] = pd.to_datetime(df["timestamp"].astype(int), unit="s")
    df = df[["date", "value", "value_classification"]]
    df.to_csv(os.path.join(DST, "crypto_fear_greed.csv"), index=False)
    print(f"  ✅ Fear&Greed: {len(df)} дней, сейчас {df['value'].iloc[0]} ({df['value_classification'].iloc[0]})")


def update_fred():
    series = {"GOLDPMGBD228NLBM": "gold_LBMA_price", "DFF": "fed_funds_rate",
              "CPIAUCSL": "inflation_CPI", "DGS10": "treasury_10y", "DTWEXBGS": "dollar_index"}
    ok = 0
    for sid, name in series.items():
        try:
            r = requests.get(f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={sid}",
                             headers=UA, timeout=(10, 30))
            r.raise_for_status()
            pd.read_csv(io.StringIO(r.text)).to_csv(os.path.join(DST, f"FRED_{name}.csv"), index=False)
            ok += 1
        except Exception:
            pass
    print(f"  {'✅' if ok else '✗'} FRED: {ok}/5 (часто медленный, можно повторить позже)")


if __name__ == "__main__":
    print("Обновляю данные для робота...")
    for name, fn in [("COT золото", update_gold_cot), ("Fear&Greed", update_fear_greed), ("FRED", update_fred)]:
        try:
            fn()
        except Exception as e:
            print(f"  ✗ {name}: {type(e).__name__}: {e}")
    print("Готово. Данные в папке Данные/")
