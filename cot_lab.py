# -*- coding: utf-8 -*-
"""
COT-лаборатория: честный, исчерпывающий тест стратегий по индексу Уильямса
на ДЛИННОЙ истории золота (2008-2026, с кризисами) — включая ШОРТ.
Запуск: python cot_lab.py

Антизаглядывание: позиция применяется на следующий день после доступного сигнала.
Проверка на устойчивость: out-of-sample (две половины) + разбор по годам-кризисам.
"""
import numpy as np
import pandas as pd

FEE = 0.0005   # 0.05% за смену позиции (фьючерсы дешевле спота)
PPY = 252      # торговых дней в году

df = pd.read_csv("Данные/gold_cot_merged.csv", parse_dates=["dt"]).sort_values("dt").reset_index(drop=True)
df["ret"] = df["close"].pct_change().fillna(0)
df["ma50"] = df["close"].rolling(50).mean()
df["ma200"] = df["close"].rolling(200).mean()
df["year"] = df["dt"].dt.year


def evaluate(pos, mask=None):
    """pos: желаемая позиция (-1/0/1) в терминах сигнала дня. Сдвигаем на +1 день."""
    d = df if mask is None else df[mask]
    p = pos.shift(1).fillna(0)
    if mask is not None:
        p = p[mask]
        ret = df["ret"][mask]
    else:
        ret = df["ret"]
    trades = p.diff().abs().fillna(0)
    strat = p * ret - trades * FEE
    eq = (1 + strat).cumprod()
    years = max((d["dt"].iloc[-1] - d["dt"].iloc[0]).days / 365.25, 0.1)
    total = eq.iloc[-1] - 1
    cagr = eq.iloc[-1] ** (1 / years) - 1
    dd = float((eq / eq.cummax() - 1).min())
    sharpe = float(strat.mean() / strat.std() * np.sqrt(PPY)) if strat.std() > 0 else 0.0
    inmkt = float((p != 0).mean())
    return dict(total=total, cagr=cagr, dd=dd, sharpe=sharpe, inmkt=inmkt)


# ── СТРАТЕГИИ (position до сдвига) ──
S = {}
S["Купи и держи"] = pd.Series(1, index=df.index)
S["COT>50 (лонг)"] = (df["comm_idx"] > 50).astype(int)
S["COT>75 (лонг строго)"] = (df["comm_idx"] > 75).astype(int)
# лонг/шорт по коммерсантам (фьючерсная логика — зарабатывает и на падении)
S["COT лонг/шорт 60-40"] = np.select([df["comm_idx"] > 60, df["comm_idx"] < 40], [1, -1], 0)
S["COT лонг/шорт 50-50"] = np.where(df["comm_idx"] > 50, 1, -1)
# COT-смещение + тренд
S["COT>50 + тренд(MA200)"] = ((df["comm_idx"] > 50) & (df["close"] > df["ma200"])).astype(int)
S["COT л/ш + тренд"] = np.select(
    [(df["comm_idx"] > 50) & (df["close"] > df["ma200"]),
     (df["comm_idx"] < 50) & (df["close"] < df["ma200"])], [1, -1], 0)
# контрариан против мелких спекулянтов («глупые деньги»)
if "smallspec_idx" in df.columns:
    S["Фейд мелких спеков"] = np.select([df["smallspec_idx"] < 25, df["smallspec_idx"] > 75], [1, -1], 0)
# чистый тренд (для сравнения — без COT)
S["Тренд MA50>MA200"] = (df["ma50"] > df["ma200"]).astype(int)

S = {k: pd.Series(v, index=df.index).astype(float) for k, v in S.items()}

# ── ПОЛНЫЙ ПЕРИОД ──
print("=" * 92)
print(f"  ЗОЛОТО 2008–2026 ({len(df)} дней) · комиссия {FEE*100:.2f}%/сделку · с антизаглядыванием")
print("=" * 92)
print(f"{'Стратегия':26} {'Доход':>10} {'CAGR':>8} {'Просадка':>9} {'Sharpe':>7} {'2013(крах)':>11} {'В рынке':>8}")
print("-" * 92)
mask2013 = df["year"] == 2013
rows = []
for name, pos in S.items():
    m = evaluate(pos)
    r13 = evaluate(pos, mask2013)["total"]
    rows.append((name, m, r13))
    print(f"{name:26} {m['total']*100:+9.0f}% {m['cagr']*100:+7.1f}% {m['dd']*100:8.1f}% {m['sharpe']:7.2f} {r13*100:+10.1f}% {m['inmkt']*100:7.0f}%")
print("-" * 92)

bh = rows[0][1]
# лучшие по CAGR и по Sharpe среди не-buyhold
cand = [r for r in rows if r[0] != "Купи и держи"]
best_cagr = max(cand, key=lambda r: r[1]["cagr"])
best_sharpe = max(cand, key=lambda r: r[1]["sharpe"])

print("\nВЕРДИКТ (полный период):")
print(f"  • Купи-держи: доход {bh['total']*100:+.0f}%, CAGR {bh['cagr']*100:+.1f}%, просадка {bh['dd']*100:.0f}%, Sharpe {bh['sharpe']:.2f}")
print(f"  • Лучшая по доходности: «{best_cagr[0]}» — CAGR {best_cagr[1]['cagr']*100:+.1f}% (buy&hold {bh['cagr']*100:+.1f}%)")
print(f"  • Лучшая по риск/доходности (Sharpe): «{best_sharpe[0]}» — Sharpe {best_sharpe[1]['sharpe']:.2f} (buy&hold {bh['sharpe']:.2f})")

# ── OUT-OF-SAMPLE: две половины ──
mid = df.index[len(df) // 2]
half1 = df.index <= mid
half2 = df.index > mid
d1, d2 = df["dt"][half1].iloc[-1].date(), df["dt"][half2].iloc[0].date()
print(f"\nПРОВЕРКА НА УСТОЙЧИВОСТЬ (out-of-sample):")
print(f"{'Стратегия':26} {'1-я пол. CAGR':>14} {'2-я пол. CAGR':>14}  вывод")
print("-" * 70)
for name, pos in S.items():
    c1 = evaluate(pos, half1)["cagr"]; c2 = evaluate(pos, half2)["cagr"]
    stable = "устойчива" if (c1 > 0 and c2 > 0) else "разваливается" if (c1 > 0) != (c2 > 0) else "слабо"
    print(f"{name:26} {c1*100:+13.1f}% {c2*100:+13.1f}%  {stable}")
