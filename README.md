# TOPIX-17 業種モメンタム・バックテスト

TOPIX-17連動ETFを用いた業種モメンタム戦略のバックテストを作成するためのPython開発環境です。

## 必要なもの

- Docker Desktop

## 開発コンテナの起動

プロジェクトのルートディレクトリで、コンテナをバックグラウンド起動します。

```powershell
docker compose up -d --build
```

起動状態は次で確認できます。

```text
docker compose ps
```

コンテナ内でPythonスクリプトを実行します。

```powershell
docker compose exec app python main.py
```

`構築成功！` が表示されます。これはスクリプトの実行結果で、開発コンテナ自体は起動したままです。

## テストを実行する

```powershell
docker compose exec app pytest
```

作業を終えたらコンテナを停止します。

```powershell
docker compose down
```

初回起動時はPythonイメージの取得と依存パッケージのインストールのため、少し時間がかかります。

コンテナには、仕様書で指定された `yfinance`、`pandas`、`numpy`、`matplotlib`、`pytest` を導入しています。
