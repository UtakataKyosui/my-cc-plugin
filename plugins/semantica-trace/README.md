# semantica-trace

過去の Claude Code セッションを decision graph として蓄積し、横断照会するプラグイン。

## 構成

| 種別 | 名前 | 役割 |
|---|---|---|
| Skill | `semantica-trace:semantica-trace` | 取り込み・バックフィル・照会の手順とモジュール構成 |
| Hook | `SessionEnd` | `hooks/ingest_session.sh` が transcript を非同期で取り込む。venv が無ければ黙って何もしない |
| MCP | `semantica-trace` | 照会専用の stdio サーバー。書き込む手段は持たない |

MCP のツール名はプラグイン経由のため `mcp__plugin_semantica-trace_semantica-trace__*` になる。

## セットアップ

隔離 venv が必要である。作り方は `skills/semantica-trace/SKILL.md` の「前提」節にある。venv が無い状態でもインストール自体は成功し、取り込みが静かに無効になるだけである。

venv の場所を変える場合は `SEMANTICA_TRACE_PYTHON` に python の実行ファイルを指定する。

## データの置き場所

- グラフ: `~/.cache/semantica-trace/data/graph-<YYYY-MM>.json`（`chmod 700`）
- 取り込みログ: `~/.cache/semantica-trace/ingest.log`（`chmod 600`）

transcript にはトークン・env ダンプ・ファイル内容が入り、グラフにも複製される。どちらも本人のみに絞ってある。
