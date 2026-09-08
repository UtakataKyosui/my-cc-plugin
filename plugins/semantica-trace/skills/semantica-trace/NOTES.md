# semantica 実 API 調査ノート（Issue #39）

このファイルは推測と実測を区別して書く。「実測」は実際に実行したコマンド・スクリプトと
その出力を根拠とする。推測は明示的に「(推測)」と書く。

隔離環境: `~/.cache/semantica-trace/.venv`（`uv venv` + `uv pip install 'semantica[all]'`、
semantica 0.6.5）。リポジトリには何もインストールしていない。

## 0. 事前に踏んだ障害: `semantica[all]` の pinecone 依存が壊れている（実測）

`uv pip install 'semantica[all]'` は成功するが、`from semantica.context import ContextGraph` が
以下の例外で **必ず失敗する**（`semantica.context.__init__` → `agent_context` →
`context_retriever` → `vector_store/__init__` → `pinecone_store.py` の import 連鎖が
パッケージ import 時に無条件で走るため、遅延 import ではない）。

```
Exception: The official Pinecone python package has been renamed from `pinecone-client`
to `pinecone`. Please remove `pinecone-client` from your project dependencies and add
`pinecone` instead.
```

原因: `semantica[all]` が依存に固定しているのは旧 `pinecone-client==6.0.0` だが、この
バージョンの `pinecone-client` は `import pinecone` した瞬間に上記の例外を送出するように
作られている（アップストリームの意図的な非推奨化）。`semantica` 側のオプション依存が
新パッケージ名に追随していないバグ。

回避策（実測、動作確認済み）:

```bash
uv pip uninstall --python ~/.cache/semantica-trace/.venv/bin/python pinecone-client
uv pip install   --python ~/.cache/semantica-trace/.venv/bin/python pinecone
```

これで `from semantica.context import ContextGraph, DecisionRecorder, Decision` が通る。
Pinecone 自体は本タスクで使わない（グラフストアは in-memory の `ContextGraph` を使う。§3）ので、
実害はインストールされた状態を import 可能にするためだけ。**ライブラリ本体
（`lib/`）はこの venv を使い、リポジトリには一切インストールしない。**

## 1. decision ノードの必須フィールドと安定 ID（実測: `context/decision_models.py` を読んだ）

`semantica.context.Decision`（dataclass）の必須フィールド:

| フィールド | 型 | 必須 | 備考 |
|---|---|---|---|
| `decision_id` | str | 実質必須 | 空文字/None なら自動で `uuid4()` が振られる。**空でない文字列を渡せばそのまま使われる**（`__post_init__` は truthy な値を上書きしない） |
| `category` | str | 必須 | 例: `tool_use` |
| `scenario` | str | 必須 | 何についての決定か（今回はユーザープロンプトの要約 or turn の説明） |
| `reasoning` | str | 必須 | 後述 §4 の理由により **thinking ブロックではなく直前の可視 text ブロック** から取る |
| `outcome` | str | 必須 | tool_result の要約 |
| `confidence` | float | 必須、0-1 | 0〜1 の範囲チェックあり。ツール呼び出しには confidence 概念がないので固定値 1.0 を使う |
| `timestamp` | datetime | 必須 | `datetime` オブジェクトである必要がある（str 不可、`from_dict` を通さない限り） |
| `decision_maker` | str | 必須 | 例: `"claude-code"` または `model` 名 |
| `metadata` | dict | 任意 | 自由形式。session_id・cwd・tool_name 等をここに詰める |

**結論: 呼び出し側は安定 ID を渡せる。** `decision_id=f"{session_id}:{message_uuid}"` を
そのまま渡してよい（実測: `Decision(decision_id="sess-A:msg-1", ...)` で uuid4 上書きは起きない）。

## 2. decision 間の因果エッジ（実測: `context/context_graph.py` を読み、実行して確認）

`context.decision_recorder.DecisionRecorder` は Neo4j 向けの Cypher クエリと、
`type(self.graph_store) is ContextGraph` のときの in-memory 分岐を両方持つ。
**`link_precedents()` の `relationship_type` は `["similar_scenario", "same_policy",
"exception_precedent"]` の enum に縛られており**（`decision_models.Precedent.__post_init__`）、
「同一セッションの前ターン」のような単純な因果関係を表すには使えない。

代わりに `ContextGraph` が直接持つ **`add_causal_relationship(source_id, target_id,
relationship_type)`** を使う。`relationship_type` は `["CAUSED", "INFLUENCED",
"PRECEDENT_FOR"]` の3種類（`context_graph.py:2005-2043`）。ソース・ターゲットの両方が
`node_type == "Decision"` のノードでないと黙って何もしない（例外は投げない）。

因果チェーンの取得は `ContextGraph.get_causal_chain(decision_id, direction="upstream"|
"downstream", max_depth=10)`（`context_graph.py:2045`）で、`CAUSED` / `INFLUENCED` /
`PRECEDENT_FOR` の3エッジタイプだけを辿る BFS。CLI の `semantica decision trace` も
最終的にこの実装（`decision_methods.get_causal_chain`)を呼ぶ。

**採用した因果エッジの張り方**: トランスクリプトの `parentUuid` チェーンを遡り、同一
session 内で直近の decision ノード（tool_use を含む assistant ターン）を見つけ、
`add_causal_relationship(prev_decision_id, this_decision_id, "CAUSED")` を張る。
単純な「直前のツール呼び出し」という線形順序ではなく、実際の会話木構造
（`parentUuid`）に従うため、将来 branch/retry のあるトランスクリプトにも対応できる。

エンティティへのリンクは `DecisionRecorder.link_entities()` が使う `ABOUT` エッジ
(`decision --[ABOUT]--> entity`) をそのまま踏襲。

## 3. グラフバックエンド: Neo4j/Oxigraph は不要。ただし CLI の decision コマンドは既定で Neo4j を要求する（実測、重要な相違点）

`semantica doctor` の出力（実測）:

```
Graph store            ✓         memory (always available)
```

しかし、CLI の `semantica decision record/list/trace/...` が内部で使う
`_get_graph_store()`（`cli.py:1083`）は:

```python
backend = cli_ctx.store_backend or graph_db.pop("backend", "neo4j")
return GraphStore(backend=backend, **graph_db)
```

で、`semantica.graph_store.GraphStore` クラス自体は `neo4j` / `falkordb` /
`neptune` / `age` の4バックエンドしかサポートしない（`graph_store/graph_store.py:566-595`、
"memory" という分岐は存在しない）。**つまり `semantica decision record` などの CLI
サブコマンドをそのまま使うと、既定で Neo4j への接続を試みて失敗する。**
doctor が言う「memory (always available)」は、CLI の decision コマンド群とは
別系統の `semantica.context.ContextGraph`（in-memory 実装、`context/context_graph.py`）
を指している。

`DecisionRecorder` は `graph_store` に何を渡すかで分岐する設計になっており
(`context/decision_recorder.py` の `type(self.graph_store) is ContextGraph` チェック)、
**`ContextGraph` を直接渡せば Neo4j 等のバックエンドは一切不要**。永続化は
`ContextGraph.save_to_file(path)` / `load_from_file(path)` で JSON ファイルへの
読み書きのみ（実測、`/tmp/test_e2e.py` で save→reload→query を確認済み）。

**結論: 本実装は semantica の CLI (`semantica decision ...`) を使わず、Python API
(`semantica.context.ContextGraph` / `Decision` / `DecisionRecorder`) を直接呼ぶ。**
docker compose 等のバックエンド起動は不要。グラフは
`~/.cache/semantica-trace/data/graph.json` に永続化する（リポジトリ外）。

## 4. 最重要の設計前提の齟齬: このマシンの transcript に thinking テキストが一切残っていない（実測、Issue のスキーマ前提と食い違う）

Issue のグラフスキーマは「直前の thinking ブロック → rationale」としているが、
実際に `~/.claude/projects/**/*.jsonl` を横断的に調べたところ:

- 6つの大きいトランスクリプト（`-Users-<user>--claude` 配下）で thinking ブロック
  417個、非空文字列は **0個**
- ランダムサンプリングした40個のトランスクリプト（複数プロジェクト）で thinking
  ブロック736個、非空文字列は **0個**

いずれも `"thinking": ""` で `signature`（API 再送信用の署名）だけが残っている。
つまりこの環境では **thinking の可視テキストが transcript に一切保存されない**
（extended thinking の内容がクライアント側で意図的に空にされているか、この
harness の設定によるもの。原因の特定はこのタスクのスコープ外）。Issue が前提と
した「thinking ブロック = rationale」は、少なくともこのマシンの transcript では
**データソースとして存在しない**。

### 代替案（採用・実測で動作確認済み）

同じトランスクリプトを調べると、assistant の可視 `text` ブロックには実際の理由説明が
豊富に入っている（例: 1トランスクリプトで text ブロック143個中143個が非空）。さらに
`parentUuid` を辿ると、**tool_use を含む assistant ターンの直前の親は、ほぼ必ず
「text のみの assistant ターン」**という構造になっている（実測、6サンプル全て一致）。

したがって rationale の抽出元を次のように変更する:

> 直前の thinking ブロック → ~~削除~~
> **`parentUuid` を遡って直近に見つかる、text を含む assistant ターンの text 本文**

thinking が存在するトランスクリプトでは thinking を優先し、存在しない場合に
この text フォールバックを使う実装にしてある（`lib/transcript_parser.py` の
`_find_rationale()`）。text も見つからない場合は `reasoning` を空文字とし、
`metadata.rationale_source = "none"` を記録して呼び出し側が判別できるようにする。

**これはスキーマを無理に捻じ曲げたものではなく、実データで検証した上での
フィールドソースの付け替えである。** グラフのフィールド名・構造（category/
scenario/reasoning/outcome/confidence/decision_maker）自体は Issue の設計通り。

### 追記（被覆率の改善、同セッション内で実施）

初版は `MAX_ANCESTOR_HOPS = 6` で打ち切っており、非空の理由は **49.7%** しかなかった。
打ち切り上限がそのまま被覆率になっていた（実測: 6→49.7% / 12→68.2% / 20→80.6% /
40→91.4% / 無制限→94.4%）。tool_use ターンは text と同居しないため（実測1064ターン中
0件）、ツール呼び出しが連続すると1回ごとに2ホップ遠ざかるのが原因。

修正は上限の撤廃ではなく **境界の導入**。直近の本物のユーザープロンプトで止め、
越えた先の text は別タスクの理由として使わない（境界越えは実測4.6%）。境界に先に
到達したらそのプロンプトを理由にし `rationale_source = "user_prompt"` を立てる。
ユーザーメッセージの注入物（slash コマンド・`<system-reminder>`・
`<local-command-stdout>`・`UserPromptSubmit` の追加コンテキスト等）は `_NOISE_PATTERNS`
で除去する（実測67件中30件前後に混入。落とさないと git status のダンプが理由になる）。

**結果: 非空の理由 100%**（1076 turn、text 89.9% / user_prompt 10.1%）。
`rationale_distance`（挟まっていた decision 数）を metadata に残し、距離2以内が65.5%、
最大37。あわせて因果親探索の O(n²) の線形走査を `_by_uuid` 索引に置き換えた。

## 5. dedup: ID キーで効くか、内容類似度で効くか（実測）

`/tmp/test_dedup.py` で確認:

- **ノード**: `ContextGraph.add_node(node_id, ...)` は内部で `self.nodes[node_id] = node`
  という辞書代入。同じ `node_id` を2回 add しても件数は増えず、後勝ちで内容が
  上書きされる。→ **ID キーで自然に冪等**。
- **エッジ**: `ContextGraph.add_edge(...)` は `edge_id` を
  `(source, target, edge_type, weight, valid_from, valid_until, metadata)` の
  決定的ハッシュ（uuid5）として計算する **が**、`_add_internal_edge()` は
  `self.edges.append(edge)` と単純追加するだけで、既存の `edge_id` との重複チェックを
  一切行わない。→ **同じエッジを2回 add すると、同じ `edge_id` を持つ要素が
  2件、リストに重複して入る（実測: `edge_count` が 1→2 に増加、
  `find_edges()` で同一 `edge_id` が2件返る)。エッジは ID キーで自然には
  冪等にならない。**
- **エンティティ ID 生成** (`EntityLinker._generate_entity_id`): `md5(f"{text}_{type}")`
  の決定的ハッシュ。**類似度ではなく完全一致方式**。同じ絶対パスの文字列を渡せば
  常に同じ ID になり、違う内容が黙って統合されることはない。ただし呼び出し側が
  file path を正規化せずに渡すと（例: 相対パス vs 絶対パス）別エンティティとして
  分裂するため、**呼び出し側でエンティティ ID の正規化は必須**（`lib/graph_ingest.py`
  の `_entity_id_for_path()` で `os.path.normpath` + 絶対パス化を行う）。

**結論と対応**: ノードは semantica 側で ID キーの冪等性が効くが、エッジは効かない。
そのため `lib/graph_ingest.py` は **エッジ追加前に `graph.find_edges(edge_type=...)`
で同一 `(source, target, edge_type)` の既存エッジを確認し、あれば `add_edge` /
`add_causal_relationship` を呼ばない**という冪等化レイヤーを自前で実装した
(`_edge_exists()`)。これにより「同じセッションを2回 ingest しても decision ノードは
上書き、エッジは重複しない」を満たす（`tests/test_idempotency.py` で確認）。

## 6. 作成したファイル

- `skills/semantica-trace/NOTES.md`（本ファイル）
- `skills/semantica-trace/lib/transcript_parser.py` — JSONL → 中間表現（turn のリスト）
- `skills/semantica-trace/lib/graph_ingest.py` — 中間表現 → ContextGraph への冪等な書き込み
- `skills/semantica-trace/lib/query.py` — セッション横断クエリのヘルパー
- `skills/semantica-trace/tests/test_idempotency.py` — 同一セッション2回 ingest で重複しないことの確認
- `skills/semantica-trace/tests/test_reproduction.py` — 第3段階の再現テスト（実トランスクリプト1本）
- `skills/semantica-trace/ingest_session.sh` — SessionEnd フックから呼ぶ薄いラッパー（第4段階、venv 解決込み）
- `skills/semantica-trace/session-end-hook-proposal.md` — settings.json への追記案とMCP登録の判断（第4段階、settings.json 自体は書き換えていない）

隔離 venv 自体（`~/.cache/semantica-trace/.venv`）とグラフデータ
（`~/.cache/semantica-trace/data/graph.json`）はリポジトリ外。

## 7. 制約への対応

- semantica MCP サーバーは照会用にのみ登録する想定だった。記録は本ライブラリが
  直接 `ContextGraph` に書き込み、MCP 経由では記録しない。ただし第4段階の調査で
  semantica 同梱の MCP サーバー自体が未検証の依存関係を持ち込むことが分かった
  ため、登録は保留した。判断の詳細は `session-end-hook-proposal.md` を参照する。
- トランスクリプトの機微情報（トークン・env ダンプ等）はグラフにもそのまま
  複製される（tool_result の内容を outcome に要約として使うため）。第4段階で
  MCP サーバーを localhost 限定にすることに加え、`~/.cache/semantica-trace/data/`
  のパーミッションを 700 にする。

## 8. SessionEnd フックの発火確認（実測）

グローバルの `settings.json` を変更せずに確認する方法として、スクラッチ配下に
`.claude/settings.json` だけを持つディレクトリを作り、そこで `claude -p` を回した。
プロジェクト設定の `SessionEnd` はユーザー設定のものを置き換えず両方が走るため、
自分のフックと sui-memory のフックが同時に発火するのも同時に観測できた。

判明したこと。

- SessionEnd は発火する。フックは同期的に呼ばれ、stdin に JSON が届く
- `nohup ... &` の子プロセスは生き残る。フック本体の exit 後に書き込みが完了した
- stdin は `transcript_path` を直接持っている。`cwd` からスラッグを組み立てる方式は
  不要だったため、`transcript_path` を優先し cwd 導出はフォールバックに落とした
- end-to-end で decision ノードと entity ノードがグラフに増えた

**先に立てた2つの疑いはどちらも誤りだった。**

1. 「`nohup ... &` の子が起動しない」— 起動しない事象は、サンドボックス下の Bash から
   手で叩いたときだけ再現するものだった。実際のフック環境では生き残る
2. 「sui-memory のログが 2026-08-13 で止まっているので background 実行パターンが
   本番で発火していない疑い」— sui-memory も同時に発火して ingest に成功した
   （ログは 66438 → 71371 バイトに増加）。SessionEnd はクリーンに終了した
   セッションでしか発火しないため、強制終了が続けばログの更新は止まる。
   **ログの日付だけを根拠にフックの故障を推定してはいけない**
