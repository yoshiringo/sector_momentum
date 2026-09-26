"""yfinance の日足取得、検証、CSVキャッシュを担当する。"""

from pathlib import Path

import pandas as pd
import yfinance as yf


REQUIRED = ("Open", "High", "Low", "Close", "Adj Close", "Volume")
OPTIONAL = ("Dividends", "Stock Splits")


def normalize_history(frame: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """取得元の列と日付を統一し、価格が使えない行を除く。"""
    if frame is None or frame.empty:
        raise ValueError(f"{ticker}: 日足データを取得できませんでした")
    data = frame.copy()
    if isinstance(data.columns, pd.MultiIndex):
        if ticker in data.columns.get_level_values(-1):
            data = data.xs(ticker, level=-1, axis=1)
        elif ticker in data.columns.get_level_values(0):
            data = data.xs(ticker, level=0, axis=1)
    missing = set(REQUIRED) - set(data.columns)
    if missing:
        raise ValueError(f"{ticker}: 必須列がありません: {', '.join(sorted(missing))}")
    for column in OPTIONAL:
        if column not in data.columns:
            data[column] = 0.0
    data = data.loc[:, [*REQUIRED, *OPTIONAL]]
    dates = pd.DatetimeIndex(pd.to_datetime(data.index))
    if dates.tz is not None:
        dates = dates.tz_convert("Asia/Tokyo").tz_localize(None)
    data.index = dates.normalize()
    data.index.name = "Date"
    data = data[~data.index.duplicated(keep="last")].sort_index()
    for column in data.columns:
        data[column] = pd.to_numeric(data[column], errors="coerce")
    for column in ("Open", "Close", "Adj Close"):
        data.loc[data[column] <= 0, column] = float("nan")
    data.loc[:, [*OPTIONAL]] = data.loc[:, [*OPTIONAL]].fillna(0.0)
    if data["Adj Close"].notna().sum() == 0:
        raise ValueError(f"{ticker}: 有効な価格がありません")
    return data


def load_history(ticker: str, cache_dir: Path, refresh: bool = False) -> pd.DataFrame:
    """CSVを再利用し、未保存または更新指定時だけ全期間を取得する。"""
    cache_file = cache_dir / f"{ticker.replace('.', '_').replace('^', '')}.csv"
    if cache_file.exists() and not refresh:
        cached = pd.read_csv(cache_file, index_col="Date", parse_dates=["Date"])
        return normalize_history(cached, ticker)
    frame = yf.Ticker(ticker).history(
        period="max", interval="1d", auto_adjust=False, actions=True,
        repair=False, raise_errors=True,
    )
    data = normalize_history(frame, ticker)
    cache_dir.mkdir(parents=True, exist_ok=True)
    data.to_csv(cache_file)
    return data


def load_all(tickers: list[str], cache_dir: Path, refresh: bool = False) -> dict[str, pd.DataFrame]:
    """必要な全銘柄を読み込み、失敗した銘柄を明示して停止する。"""
    result = {}
    for ticker in tickers:
        try:
            result[ticker] = load_history(ticker, cache_dir, refresh)
        except Exception as exc:
            raise RuntimeError(f"{ticker} のデータ取得に失敗しました: {exc}") from exc
    return result
