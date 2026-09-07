# obsidian-semantic-search

Obsidian Vault を **ローカルの埋め込みモデル**で意味検索（セマンティック検索）する Claude Code
プラグイン。LLM（Claude）に検索させるのではなく、独立した Python 検索エンジンがノートをベクトル化し、
numpy の総当たりコサイン類似度で関連ノートを返す。Vault の内容を外部に送信しない。

既存の `obsidian-knowledge`（Obsidian CLI のキーワード全文検索）とは棲み分ける。キーワードが
思い出せない・言い回しが違う・概念的に関連する、といった全文一致では拾えない検索に使う。

## アーキテクチャ

```
search/obsidian_semantic_search/   # Python パッケージ（検索エンジン本体）
bin/oss                            # CLI ラッパ（venv / uv を吸収）
setup.sh                           # 依存セットアップ（uv 優先 + venv フォールバック）
skills/obsidian-semantic-search/   # オンデマンド検索 Skill
hooks/                             # SessionStart でインデックス鮮度をチェック
```

インデックスは `<vault>/.obsidian-semantic-index/`（gitignore 対象）に保存される。
`embeddings.npy`（float32 行列）+ `chunks.jsonl`（メタデータ）+ `manifest.json`（モデル・mtime）。

## セットアップ

```bash
bash setup.sh
```

`uv` があれば `uv venv` + `uv pip install`、無ければ `python3 -m venv` + `pip` を使う。
初回は埋め込みモデル（既定 `intfloat/multilingual-e5-small`, 約120MB）を Hugging Face から
ダウンロードする。以降はオフラインで動作する。

## 使い方

```bash
bin/oss index            # 増分インデックス（変更ファイルのみ再埋め込み）
bin/oss index --full     # 全再構築（モデル変更時・破損時）
bin/oss query "曖昧な検索語" --json --top-k 5
bin/oss status --json    # インデックスの状態（モデルを読み込まず高速）
```

`query --json` の出力:

```json
{"query":"...","model":"intfloat/multilingual-e5-small","results":[
  {"path":"knowledge/...","score":0.82,"heading":"...","line_start":17,"snippet":"..."}]}
```

## 環境変数

| 変数 | 既定 | 説明 |
|---|---|---|
| `OBSIDIAN_SEMANTIC_VAULT_DIR` | （`OBSIDIAN_VAULT_PATH` → `.obsidian` 探索 → cwd） | 検索対象 Vault ルート |
| `OBSIDIAN_SEMANTIC_INDEX_DIR` | `<vault>/.obsidian-semantic-index` | インデックス保存先 |
| `OBSIDIAN_SEMANTIC_MODEL` | `intfloat/multilingual-e5-small` | 埋め込みモデル（例: `cl-nagoya/ruri-v3-30m`） |

モデルを変更したら `bin/oss index --full` で再構築する（次元が変わるため）。

## チャンク分割と入力上限

ノートは見出し（H1-H3）単位でチャンクに分割し、各チャンク先頭に「ファイルタイトル > 見出し
パンくず」を付与する。チャンク長の既定は **480 文字**で、これは既定モデル
`intfloat/multilingual-e5-small` の入力上限 **512 トークン**に収めるための値（日本語は概ね
1 文字 ≲ 1 トークン）。上限を超える入力は SentenceTransformer が無言で末尾を切り捨てるため、
パンくず連結後の実テキストが 480 文字を超えないよう本文側の予算を調整している。

入力上限が大きい別モデル（`OBSIDIAN_SEMANTIC_MODEL`）に切り替える場合は、`chunker.py` の
`_DEFAULT_MAX_CHARS` を引き上げてから `index --full` するとより長い文脈を 1 チャンクに収められる。

## テスト

```bash
cd search
python -m unittest discover -s tests           # 全テスト（store/indexer/search は numpy 必須）
python3 -m unittest tests.test_chunker          # 依存なしで走る純粋ロジック
```

## 補足

- Python 3.14 等で wheel が未提供の場合は `uv venv --python 3.12` で venv を作り直す。
- 重い `index` は SessionStart フックでは実行しない（未構築/陳腐化の通知のみ）。再構築は Skill / 手動で行う。
