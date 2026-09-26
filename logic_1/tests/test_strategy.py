"""既知の価格系列で順位付けと売買時系列を検証する。"""

from datetime import date

import pandas as pd
import pytest

from logic_1.config import BENCHMARK, SECTORS, BacktestConfig
from logic_1.src.backtest import run_backtest
from logic_1.src.momentum import build_rankings, monthly_return
from logic_1.src.reporter import summary_table


def history(
    dates: list[str] | pd.DatetimeIndex, opens: list[float], closes: list[float],
    adjusted: list[float] | None = None, dividends: list[float] | None = None,
) -> pd.DataFrame:
    """テスト用の日足価格と分配金系列を作る。"""
    return pd.DataFrame(
        {"Open": opens, "Close": closes, "Adj Close": adjusted or closes,
         "Dividends": dividends or [0.0] * len(opens)},
        index=pd.to_datetime(dates),
    )


def test_monthly_return_requires_exact_calendar_month() -> None:
    """3か月前の暦月が欠けた場合に別の月で代用しない。"""
    prices = pd.Series([100.0, 115.0], index=pd.PeriodIndex(["2024-11", "2025-02"], freq="M"))
    assert monthly_return(prices, pd.Period("2025-02", freq="M"), 3) == pytest.approx(0.15)
    assert monthly_return(prices, pd.Period("2025-02", freq="M"), 6) is None


def test_rankings_use_adjusted_monthly_prices_and_relative_score() -> None:
    """既知の価格から相対リターン、スコア、同点順位を求める。"""
    dates = pd.date_range("2024-01-31", periods=15, freq="ME")
    histories = {ticker: history(dates, [100.0] * 15, [100.0] * 15)
                 for ticker in SECTORS}
    histories[BENCHMARK] = history(dates, [100.0] * 15, [100.0] * 15)
    adjusted = [100.0] * 13 + [110.0, 110.0]
    histories["1617.T"] = history(dates, [100.0] * 15, [100.0] * 15, adjusted)
    config = BacktestConfig(top_n=3)
    rankings, _ = build_rankings(histories, config, today=date(2025, 4, 1))
    february = rankings[rankings["signal_date"] == pd.Timestamp("2025-02-28")]
    assert february.iloc[0]["ticker"] == "1617.T"
    assert february.iloc[0]["return_3m"] == pytest.approx(0.10)
    assert february.iloc[0]["relative_return_6m"] == pytest.approx(0.10)
    assert february.iloc[0]["momentum_score"] == pytest.approx(0.10)
    assert february.iloc[1]["ticker"] == "1618.T"
    assert february["selected"].sum() == 3


def test_next_open_rebalance_and_dividend() -> None:
    """シグナル翌日の始値で売買し、分配金を売買前口数へ加算する。"""
    dates = ["2025-01-31", "2025-02-03", "2025-02-28", "2025-03-03"]
    histories = {
        BENCHMARK: history(dates, [100, 100, 100, 100], [100, 100, 100, 100]),
        "1617.T": history(dates, [10, 10, 20, 30], [10, 10, 20, 30]),
        "1618.T": history(dates, [20, 20, 20, 20], [20, 20, 20, 20], dividends=[0, 0, 0, 2]),
        "1619.T": history(dates, [10, 10, 10, 10], [10, 10, 10, 10]),
    }
    rankings = pd.DataFrame([
        {"signal_date": pd.Timestamp("2025-01-31"), "rank": 1, "ticker": "1617.T", "selected": True},
        {"signal_date": pd.Timestamp("2025-01-31"), "rank": 2, "ticker": "1618.T", "selected": True},
        {"signal_date": pd.Timestamp("2025-02-28"), "rank": 1, "ticker": "1617.T", "selected": True},
        {"signal_date": pd.Timestamp("2025-02-28"), "rank": 2, "ticker": "1619.T", "selected": True},
    ])
    result = run_backtest(histories, rankings, BacktestConfig(initial_cash=300, top_n=2))
    first = result.trades[result.trades["date"] == pd.Timestamp("2025-02-03")]
    assert set(first["ticker"]) == {"1617.T", "1618.T"}
    assert first.set_index("ticker").at["1617.T", "price"] == 10
    assert result.trades["date"].min() > pd.Timestamp("2025-01-31")
    last = result.holdings[result.holdings["date"] == pd.Timestamp("2025-03-03")]
    assert set(last["ticker"]) == {"1617.T", "1619.T"}
    assert last["weight"].tolist() == [0.5, 0.5]
    assert last["market_value"].tolist() == pytest.approx([307.5, 307.5])
    assert result.daily.iloc[-1]["portfolio_value"] == pytest.approx(615.0)
    assert summary_table(result, BacktestConfig(initial_cash=300, top_n=2)).set_index("metric").at["trades", "strategy"] == 5


def test_missing_open_delays_execution() -> None:
    """対象ETFの始値が欠けると共通の次取引日まで売買を待つ。"""
    dates = ["2025-01-31", "2025-02-03", "2025-02-04"]
    histories = {
        BENCHMARK: history(dates, [100, 100, 100], [100, 100, 100]),
        "1617.T": history(dates, [10, float("nan"), 12], [10, 11, 12]),
    }
    rankings = pd.DataFrame([
        {"signal_date": pd.Timestamp("2025-01-31"), "rank": 1,
         "ticker": "1617.T", "selected": True}
    ])
    result = run_backtest(histories, rankings, BacktestConfig(initial_cash=120, top_n=1))
    assert result.trades.iloc[0]["date"] == pd.Timestamp("2025-02-04")
    assert result.trades.iloc[0]["price"] == 12
    assert result.daily.iloc[0]["benchmark_value"] == pytest.approx(120)
