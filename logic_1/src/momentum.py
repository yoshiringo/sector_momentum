"""月末価格から相対モメンタムと業種順位を求める。"""

from datetime import date

import pandas as pd

from logic_1.config import BENCHMARK, SECTORS, BacktestConfig


def monthly_closes(frame: pd.DataFrame) -> pd.Series:
    """各暦月の最後に存在する調整済み終値を取り出す。"""
    return frame["Adj Close"].groupby(frame.index.to_period("M")).last()


def monthly_return(prices: pd.Series, month: pd.Period, months: int) -> float | None:
    """指定月と指定か月前の月末価格から騰落率を計算する。"""
    previous = month - months
    if month not in prices.index or previous not in prices.index:
        return None
    current_price = prices.loc[month]
    previous_price = prices.loc[previous]
    if pd.isna(current_price) or pd.isna(previous_price) or previous_price <= 0:
        return None
    return float(current_price / previous_price - 1)


def build_rankings(
    histories: dict[str, pd.DataFrame], config: BacktestConfig,
    today: date | None = None,
) -> tuple[pd.DataFrame, list[str]]:
    """確定した各月末について17業種の順位と選択対象を作る。"""
    today = today or date.today()
    benchmark = histories[BENCHMARK]
    benchmark_monthly = monthly_closes(benchmark)
    sector_monthly = {ticker: monthly_closes(histories[ticker]) for ticker in SECTORS}
    end = pd.Timestamp(config.end or today)
    start = pd.Timestamp(config.start) if config.start else benchmark.index.min()
    rows: list[dict] = []
    logs: list[str] = []
    signal_index = benchmark.index[benchmark["Adj Close"].notna()]
    periods = signal_index.to_period("M")
    for month in sorted(periods.unique()):
        # 次の月の取引日がキャッシュにあれば、月末まで取得済みと確認できる。
        if month + 1 not in periods:
            continue
        dates = signal_index[periods == month]
        signal_date = dates.max()
        if signal_date < start or signal_date > end or month >= pd.Period(today, freq="M"):
            continue
        benchmark_returns = {
            months: monthly_return(benchmark_monthly, month, months)
            for months in config.momentum_weights
        }
        if any(value is None for value in benchmark_returns.values()):
            continue
        candidates: list[dict] = []
        for ticker, sector in SECTORS.items():
            frame = histories[ticker]
            current_month_rows = frame.loc[
                (frame.index.to_period("M") == month) & (frame.index <= signal_date)
            ].dropna(subset=["Adj Close"])
            if current_month_rows.empty:
                continue
            prices = sector_monthly[ticker].copy()
            prices.loc[month] = float(current_month_rows["Adj Close"].iloc[-1])
            returns = {
                months: monthly_return(prices, month, months)
                for months in config.momentum_weights
            }
            if any(value is None for value in returns.values()):
                continue
            relative = {months: returns[months] - benchmark_returns[months] for months in returns}
            score = sum(relative[months] * weight for months, weight in config.momentum_weights.items())
            row = {"signal_date": signal_date, "ticker": ticker, "sector": sector,
                   "momentum_score": score}
            for months in (3, 6, 12):
                row[f"return_{months}m"] = returns.get(months, float("nan"))
                row[f"nikkei_return_{months}m"] = benchmark_returns.get(months, float("nan"))
                row[f"relative_return_{months}m"] = relative.get(months, float("nan"))
            candidates.append(row)
        candidates.sort(key=lambda row: (-row["momentum_score"], row["ticker"]))
        selected = [row["ticker"] for row in candidates[:config.top_n]]
        leaders = ", ".join(
            f"{row['ticker']}={row['momentum_score']:.4f}"
            for row in candidates[:config.top_n]
        )
        logs.append(
            f"{signal_date.date()} Signal: {len(candidates)}/{len(SECTORS)} eligible; "
            f"selected {leaders or '-'}"
        )
        for rank, row in enumerate(candidates, start=1):
            row["rank"] = rank
            row["selected"] = rank <= config.top_n
            rows.append(row)
    columns = ["signal_date", "rank", "ticker", "sector", "return_3m", "return_6m",
               "return_12m", "nikkei_return_3m", "nikkei_return_6m", "nikkei_return_12m",
               "relative_return_3m", "relative_return_6m", "relative_return_12m",
               "momentum_score", "selected"]
    return pd.DataFrame(rows, columns=columns), logs
