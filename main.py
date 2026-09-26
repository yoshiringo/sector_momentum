"""複数のバックテスト方針に共通する実行入口。"""

import argparse
from logic_1.cli import main as run_logic_1


def create_parser() -> argparse.ArgumentParser:
    """共通の方針選択オプションだけを受け取り、他の引数を方針へ渡す。"""
    parser = argparse.ArgumentParser(add_help=False, description="バックテストの方針を選択する")
    parser.add_argument("--logic", choices=("logic_1",), default="logic_1", help="実行する方針")
    return parser


def main() -> None:
    """選択された方針へCLI引数を渡してバックテストを開始する。"""
    args, strategy_args = create_parser().parse_known_args()
    if args.logic == "logic_1":
        run_logic_1(strategy_args)


if __name__ == "__main__":
    main()
