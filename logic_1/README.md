# TOPIX-17 業種モメンタム・バックテスト

TOPIX-17連動ETFの月次相対モメンタムを日経平均と比較し、上位業種を均等保有する戦略を検証します。初期設定は3・6・12か月の相対リターンを50%・30%・20%で合成し、上位3業種に投資します。元の仕様は [spec.md](spec.md) にあります。

## セットアップと実行

Python 3.11以上で実行します。

```powershell
pip install -r requirements.txt
python main.py --logic logic_1
```

Dockerを使う場合は次のとおりです。

```powershell
docker compose up -d --build
docker compose exec app python main.py --logic logic_1
```

初回実行時にyfinanceから17 ETFと日経平均の日足を取得し、`data/raw/` に銘柄別CSVを保存します。通常は保存済みCSVを使用します。最新データを反映する際は `--refresh-data` を指定してください。取得元の仕様や過去データの修正により、更新後の結果が変わることがあります。

## CLI

```powershell
python main.py --logic logic_1 --start 2015-01-01 --end 2025-12-31
python main.py --logic logic_1 --initial-cash 1000000 --top-n 5
python main.py --logic logic_1 --refresh-data --verbose
python main.py --logic logic_1 --output-dir output/custom --cache-dir data/raw
```

`--start` と `--end` は両端を含みます。開始日前の価格はモメンタム計算に使用します。指定期間内で確定した最初の月末シグナルの翌取引日から投資します。月途中で終了する場合、その月のシグナルは作りません。ウェイトを変更する場合は `logic_1/config.py` の `momentum_weights` を編集してください。ウェイトの合計は1にします。

## 計算方法

各月の最終取引日の調整済み終値でETFと日経平均の3・6・12か月リターンを計算し、差にウェイトを掛けて順位付けします。売買にはyfinanceの `auto_adjust=False` の `Open` を使用し、シグナル日の次に必要な全ETFの始値が揃う取引日で均等配分します。同じ銘柄が続いても毎月配分を戻します。売買コスト、税金、スリッページは0、口数は小数可です。

ETFの分配金は権利落ち日に、売買前の保有口数に応じて現金へ加えます。yfinanceの履歴は支払日を示さないため、実際より早く再投資される場合があります。yfinanceの過去OHLCには分割調整が含まれるため、分割イベントを保有口数へ重ねて適用しません。日経平均は同じ初回投資日の始値で仮想購入し、その後保有し続けます。

欠損価格は補完しません。必要な過去月末価格がないETFはその月の順位から除外します。売買に必要な始値が欠ける場合は共通の始値が揃う日まで待ち、次のシグナルまでに揃わなければ見送ります。保有ETFの終値が欠ける日は日次評価から除外します。`--verbose` で対象銘柄数、売買日、欠損日のログを確認できます。

## 出力とテスト

`output/logic_1/` に `portfolio_daily.csv`、`monthly_rankings.csv`、`trades.csv`、`holdings.csv`、`summary.csv`、`equity_curve.png`、`drawdown.png` を保存します。CAGRは初回投資日から最終評価日までの暦日数で、年率ボラティリティとシャープレシオは日次リターンと252取引日で計算します。無リスク金利は0です。

```powershell
pytest
# または
docker compose exec app pytest
```

この検証は現在存在するETFの過去価格を使用します。ETFの信託報酬、需給、追跡誤差が含まれ、TOPIX-17指数そのものの検証ではありません。過去の成績は将来の成果を保証しません。
