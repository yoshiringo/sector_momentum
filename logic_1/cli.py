"""TOPIX-17 業種モメンタム・バックテストのCLI。"""

import argparse
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from logic_1.config import BENCHMARK, SECTORS, BacktestConfig
from logic_1.src.backtest import run_backtest
from logic_1.src.data_loader import load_all
from logic_1.src.momentum import build_rankings
from logic_1.src.reporter import print_summary, summary_table, write_outputs


def parse_date(value: str) -> date:
    """CLIの日付をISO形式で読み取り、入力誤りを表示する。"""
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("日付は YYYY-MM-DD で指定してください") from exc


def create_parser() -> argparse.ArgumentParser:
    """期間、資金、保有数、データ更新などのCLI引数を定義する。"""
    parser = argparse.ArgumentParser(description="TOPIX-17 業種モメンタム・バックテスト")
    parser.add_argument("--start", type=parse_date, help="バックテスト開始日 (YYYY-MM-DD)")
    parser.add_argument("--end", type=parse_date, help="バックテスト終了日 (YYYY-MM-DD、当日を含む)")
    parser.add_argument("--initial-cash", type=float, default=500_000, help="初期資金 (JPY)")
    parser.add_argument("--top-n", type=int, default=3, help="均等保有する上位業種数")
    parser.add_argument("--refresh-data", action="store_true", help="yfinanceから全銘柄を再取得する")
    parser.add_argument("--verbose", action="store_true", help="月次シグナルと欠損日の詳細を表示する")
    parser.add_argument("--output-dir", type=Path, default=Path("output/logic_1"), help="結果の保存先")
    parser.add_argument("--cache-dir", type=Path, default=Path("data/raw"), help="日足CSVの保存先")
    return parser


def main(argv: list[str] | None = None) -> None:
    """設定を検証し、データ取得からレポート作成まで実行する。"""
    parser = create_parser()
    args = parser.parse_args(argv)
    config = BacktestConfig(start=args.start, end=args.end,
                            initial_cash=args.initial_cash, top_n=args.top_n)
    try:
        config.validate()
        histories = load_all([*SECTORS, BENCHMARK], args.cache_dir, args.refresh_data)
        today = datetime.now(ZoneInfo("Asia/Tokyo")).date()
        rankings, logs = build_rankings(histories, config, today=today)
        result = run_backtest(histories, rankings, config, logs)
        summary = summary_table(result, config)
        write_outputs(result, summary, args.output_dir)
    except (ValueError, RuntimeError) as exc:
        parser.exit(1, f"Error: {exc}\n")
    print_summary(result, summary, config)
    print(f"\nSaved results to {args.output_dir}")
    if args.verbose:
        print("\n".join(result.logs))
