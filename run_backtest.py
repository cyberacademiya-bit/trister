# -*- coding: utf-8 -*-
"""
Точка входа. Запуск:  python run_backtest.py

Тянет данные → прогоняет стратегию → печатает честный отчёт.
"""
import config
import data
import strategy
import backtest


def _pct(x):
    return f"{x * 100:+.2f}%"


def main():
    print("=" * 56)
    print("  ТРИСТЕР — бэктест (Фаза 1)")
    print("=" * 56)
    print(f"Рынок      : {config.SYMBOL} @ {config.EXCHANGE}")
    print(f"Таймфрейм  : {config.TIMEFRAME},  история: {config.SINCE_DAYS} дн.")
    print(f"Стратегия  : SMA crossover ({config.FAST}/{config.SLOW})")
    print(f"Капитал    : {config.INITIAL_CAPITAL:.0f} USDT,  комиссия: {config.FEE*100:.2f}%/сделку")
    print("-" * 56)

    print("Загружаю данные...")
    df = data.fetch_ohlcv()
    print(f"Свечей: {len(df)}  ({df['dt'].iloc[0]} → {df['dt'].iloc[-1]})")

    df = strategy.sma_crossover(df)
    df, m = backtest.run(df)

    print("-" * 56)
    print("  РЕЗУЛЬТАТ")
    print("-" * 56)
    print(f"Итоговый капитал   : {m['final_equity']:.2f} USDT")
    print(f"Доход стратегии    : {_pct(m['total_return'])}")
    print(f"Купил-и-держи (B&H): {_pct(m['buy_hold_return'])}   ← эталон")
    print(f"Сделок             : {m['trades']}")
    print(f"Winrate            : {m['winrate']*100:.1f}%")
    print(f"Макс. просадка     : {_pct(m['max_drawdown'])}")
    print(f"Sharpe (годовой)   : {m['sharpe']:.2f}")
    print("-" * 56)

    # честный вердикт
    beat = m["total_return"] - m["buy_hold_return"]
    if m["total_return"] <= 0:
        verdict = "❌ Стратегия в МИНУСЕ. В таком виде торговать нельзя."
    elif beat <= 0:
        verdict = "⚠️  В плюсе, но ПРОИГРАЛА buy & hold. Смысла нет — проще купить и держать."
    else:
        verdict = f"✅ Обыграла buy & hold на {_pct(beat)}. Есть на что смотреть (но нужен тест на других периодах)."
    print(verdict)
    print("=" * 56)


if __name__ == "__main__":
    main()
