"""パフォーマンス指標、CSV、グラフ、コンソール出力を作る。"""

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from logic_1.config import BacktestConfig
from logic_1.src.backtest import BacktestResult


def _metrics(
    values: pd.Series, initial_cash: float, valid_returns: pd.Series | None = None,
) -> dict[str, float]:
    """同じ日次資産系列から累積収益とリスク指標を計算する。"""
    values = values.astype(float)
    start = pd.Timestamp(values.index[0])
    end = pd.Timestamp(values.index[-1])
    years = (end - start).days / 365.25
    if valid_returns is None:
        returns = values.pct_change().dropna()
        first_return = values.iloc[0] / initial_cash - 1
        returns = pd.concat([pd.Series([first_return]), returns], ignore_index=True)
    else:
        returns = valid_returns.dropna().reset_index(drop=True)
    volatility = float(returns.std(ddof=1) * np.sqrt(252)) if len(returns) > 1 else float("nan")
    sharpe = float(returns.mean() / returns.std(ddof=1) * np.sqrt(252)) if volatility > 0 else float("nan")
    curve = pd.concat([pd.Series([initial_cash]), values.reset_index(drop=True)], ignore_index=True)
    drawdown = curve / curve.cummax() - 1
    return {
        "initial_value": initial_cash,
        "final_value": float(values.iloc[-1]),
        "total_return": float(values.iloc[-1] / initial_cash - 1),
        "cagr": float((values.iloc[-1] / initial_cash) ** (1 / years) - 1) if years > 0 else float("nan"),
        "max_drawdown": float(drawdown.min()),
        "annual_volatility": volatility,
        "sharpe_ratio": sharpe,
    }


def summary_table(result: BacktestResult, config: BacktestConfig) -> pd.DataFrame:
    """戦略と日経平均の同期間の指標を一つの表にまとめる。"""
    daily = result.daily.set_index("date")
    strategy = _metrics(daily["portfolio_value"], config.initial_cash,
                        daily["daily_return"])
    benchmark_returns = daily["benchmark_value"].pct_change()
    benchmark_returns.iloc[0] = daily["benchmark_value"].iloc[0] / config.initial_cash - 1
    benchmark_returns = benchmark_returns.where(daily["daily_return"].notna())
    benchmark = _metrics(daily["benchmark_value"], config.initial_cash,
                         benchmark_returns)
    strategy["trades"] = len(result.trades)
    benchmark["trades"] = 1
    return pd.DataFrame({"metric": list(strategy), "strategy": list(strategy.values()),
                         "benchmark": [benchmark[key] for key in strategy]})


def print_summary(result: BacktestResult, summary: pd.DataFrame, config: BacktestConfig) -> None:
    """主要指標と日経平均との差を端末に表示する。"""
    data = summary.set_index("metric")
    first = result.daily["date"].iloc[0].date()
    last = result.daily["date"].iloc[-1].date()
    print(f"Backtest Result  {first} - {last}")
    print(f"Initial Capital: {config.initial_cash:,.0f} JPY")
    for label, column in (("Strategy", "strategy"), ("Nikkei 225", "benchmark")):
        print(f"\n{label}")
        print(f"Final Value: {data.at['final_value', column]:,.0f} JPY")
        for metric, name in (("total_return", "Total Return"), ("cagr", "CAGR"),
                             ("max_drawdown", "Maximum Drawdown"),
                             ("annual_volatility", "Annual Volatility")):
            print(f"{name}: {data.at[metric, column]:.2%}")
        print(f"Sharpe Ratio: {data.at['sharpe_ratio', column]:.2f}")
        print(f"Trades: {data.at['trades', column]:.0f}")
    excess = data.at["total_return", "strategy"] - data.at["total_return", "benchmark"]
    print(f"\nStrategy Excess Return: {excess * 100:+.2f} percentage points")


def write_outputs(result: BacktestResult, summary: pd.DataFrame, output_dir: Path) -> None:
    """仕様書の5種類のCSVと2種類のPNGを保存する。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, frame in (("portfolio_daily", result.daily), ("monthly_rankings", result.rankings),
                        ("trades", result.trades), ("holdings", result.holdings),
                        ("summary", summary)):
        frame.to_csv(output_dir / f"{name}.csv", index=False)
    dates = pd.to_datetime(result.daily["date"])
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(dates, result.daily["portfolio_value"], label="Strategy")
    ax.plot(dates, result.daily["benchmark_value"], label="Nikkei 225")
    ax.set(xlabel="Date", ylabel="Portfolio Value", title="Equity Curve")
    ax.legend()
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "equity_curve.png")
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.plot(dates, result.daily["drawdown"] * 100)
    ax.set(xlabel="Date", ylabel="Drawdown (%)", title="Strategy Drawdown")
    fig.autofmt_xdate()
    fig.tight_layout()
    fig.savefig(output_dir / "drawdown.png")
    plt.close(fig)
