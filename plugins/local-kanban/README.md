# local-kanban

外部サービスを使わずにカンバンボードを扱うプラグイン。

## 構成

| 種別 | 名前 | 役割 |
|---|---|---|
| Skill | `local-kanban:local-kanban` | `scripts/kanban.py` によるボード操作の手順 |

## データの置き場所

作業ディレクトリの `.kanban/board.json`。リポジトリごとに独立したボードになるため、追跡したくない場合は `.gitignore` に `.kanban/` を足す。

## 依存

- `python3`（標準ライブラリのみ）
