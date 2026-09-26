"""月末シグナルと翌取引日始値の売買を時系列で処理する。"""

from dataclasses import dataclass

import pandas as pd

from logic_1.config import BENCHMARK, SECTORS, BacktestConfig


@dataclass
class BacktestResult:
    """出力と成績計算に渡すバックテストの全履歴。"""

    daily: pd.DataFrame
    rankings: pd.DataFrame
    trades: pd.DataFrame
    holdings: pd.DataFrame
    logs: list[str]


def _price(history: pd.DataFrame, day: pd.Timestamp, column: str) -> float | None:
    """指定日に存在する有効な価格だけを返す。"""
    if day not in history.index:
        return None
    value = history.at[day, column]
    if pd.isna(value) or value <= 0:
        return None
    return float(value)


def _rebalance(
    day: pd.Timestamp, selected: list[str], positions: dict[str, float], cash: float,
    histories: dict[str, pd.DataFrame], trades: list[dict], holdings: list[dict],
) -> float:
    """始値で既存保有を売却・調整し、選択銘柄を均等配分にする。"""
    tickers = sorted(set(positions) | set(selected))
    opens = {ticker: _price(histories[ticker], day, "Open") for ticker in tickers}
    if any(price is None for price in opens.values()):
        raise ValueError("売買に必要な始値がありません")
    equity = cash + sum(positions[ticker] * opens[ticker] for ticker in positions)
    target_value = equity / len(selected)
    changes = {
        ticker: (target_value / opens[ticker] if ticker in selected else 0.0)
        - positions.get(ticker, 0.0)
        for ticker in tickers
    }
    for action, predicate in (("SELL", lambda change: change < -1e-10),
                              ("BUY", lambda change: change > 1e-10)):
        for ticker in tickers:
            change = changes[ticker]
            if not predicate(change):
                continue
            quantity = abs(change)
            amount = quantity * opens[ticker]
            cash += amount if action == "SELL" else -amount
            positions[ticker] = positions.get(ticker, 0.0) + change
            trades.append({"date": day, "ticker": ticker, "sector": SECTORS[ticker],
                           "action": action, "price": opens[ticker],
                           "quantity": quantity, "amount": amount})
    positions.update({ticker: target_value / opens[ticker] for ticker in selected})
    for ticker in list(positions):
        if ticker not in selected:
            del positions[ticker]
    cash = 0.0 if abs(cash) < 1e-6 else cash
    for ticker in selected:
        holdings.append({"date": day, "ticker": ticker, "sector": SECTORS[ticker],
                         "quantity": positions[ticker], "price": opens[ticker],
                         "market_value": target_value, "weight": 1 / len(selected)})
    return cash


def run_backtest(
    histories: dict[str, pd.DataFrame], rankings: pd.DataFrame,
    config: BacktestConfig, signal_logs: list[str] | None = None,
) -> BacktestResult:
    """初回投資から終了日まで売買、分配金、日次時価評価を進める。"""
    benchmark = histories[BENCHMARK]
    end = pd.Timestamp(config.end) if config.end else benchmark.index.max()
    signal_groups = {
        pd.Timestamp(day): group.sort_values("rank").loc[lambda part: part["selected"], "ticker"].tolist()
        for day, group in rankings.groupby("signal_date")
    }
    positions: dict[str, float] = {}
    cash = config.initial_cash
    benchmark_quantity: float | None = None
    first_day: pd.Timestamp | None = None
    pending: tuple[pd.Timestamp, list[str]] | None = None
    trade_rows: list[dict] = []
    holding_rows: list[dict] = []
    daily_rows: list[dict] = []
    logs = list(signal_logs or [])
    previous_value: float | None = None
    peak = config.initial_cash

    for day in benchmark.index[benchmark.index <= end]:
        # 権利落ち日の保有判定には、その日の売買前の口数を使う。
        for ticker, quantity in positions.items():
            if day in histories[ticker].index:
                dividend = histories[ticker].at[day, "Dividends"]
                if pd.notna(dividend) and dividend > 0:
                    cash += quantity * float(dividend)

        if pending is not None and day > pending[0]:
            required = set(positions) | set(pending[1])
            if first_day is None:
                benchmark_open = _price(benchmark, day, "Open")
            else:
                benchmark_open = 1.0
            ready = benchmark_open is not None and all(
                _price(histories[ticker], day, "Open") is not None for ticker in required
            )
            if ready:
                cash = _rebalance(day, pending[1], positions, cash, histories,
                                  trade_rows, holding_rows)
                if first_day is None:
                    first_day = day
                    benchmark_quantity = config.initial_cash / benchmark_open
                delay = " (delayed)" if (day.to_period("M") - pending[0].to_period("M")).n > 1 else ""
                logs.append(f"{pending[0].date()} signal executed {day.date()}{delay}")
                pending = None

        if first_day is not None:
            close_prices = {ticker: _price(histories[ticker], day, "Close") for ticker in positions}
            benchmark_close = _price(benchmark, day, "Close")
            if benchmark_close is None or any(value is None for value in close_prices.values()):
                logs.append(f"{day.date()} valuation skipped: missing close")
                previous_value = None
            else:
                value = cash + sum(positions[ticker] * close_prices[ticker] for ticker in positions)
                peak = max(peak, value)
                daily_return = (value / previous_value - 1) if previous_value else (
                    value / config.initial_cash - 1 if day == first_day else float("nan")
                )
                daily_rows.append({"date": day, "portfolio_value": value, "cash": cash,
                                   "benchmark_value": benchmark_quantity * benchmark_close,
                                   "daily_return": daily_return,
                                   "drawdown": value / peak - 1})
                previous_value = value

        if day in signal_groups:
            if pending is not None:
                logs.append(f"{pending[0].date()} signal skipped: no common execution open before next signal")
            selected = signal_groups[day]
            pending = (day, selected) if selected else None

    if pending is not None:
        logs.append(f"{pending[0].date()} signal not executed within the requested period")
    if not daily_rows:
        raise ValueError("指定期間内に投資と日次評価を開始できませんでした")
    return BacktestResult(
        daily=pd.DataFrame(daily_rows), rankings=rankings,
        trades=pd.DataFrame(trade_rows, columns=["date", "ticker", "sector", "action", "price", "quantity", "amount"]),
        holdings=pd.DataFrame(holding_rows, columns=["date", "ticker", "sector", "quantity", "price", "market_value", "weight"]),
        logs=logs,
    )
