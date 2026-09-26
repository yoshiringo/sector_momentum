# バックテストプロジェクト

投資方針ごとにコードと結果を分けて管理する Python プロジェクトです。Python 3.11 以上を使用します。

## セットアップ

```powershell
pip install -r requirements.txt
```

Docker を使う場合は、プロジェクトのルートで起動します。

```powershell
docker compose up -d --build
```

## 方針一覧と実行方法

| 方針 | 内容 | 詳細 |
|---|---|---|
| `logic_1` | TOPIX-17 業種モメンタム | [説明](logic_1/README.md)・[仕様書](logic_1/spec.md) |

```powershell
python main.py --logic logic_1
python main.py --logic logic_1 --start 2015-01-01 --end 2025-12-31
```

`python main.py` は `logic_1` を実行します。Docker では `docker compose exec app python main.py --logic logic_1` を使います。方針固有の引数と計算方法は各方針の README を参照してください。

価格キャッシュは `data/raw/` で共有し、結果は方針ごとに `output/<方針名>/` へ保存します。共通の依存パッケージ、Docker 設定、テスト設定はプロジェクトのルートにあります。

```powershell
pytest
# または
docker compose exec app pytest
```
