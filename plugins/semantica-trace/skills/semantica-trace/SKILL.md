---
name: semantica-trace
description: Claude Code の過去セッションにおけるエージェントの決定の流れを、semantica の decision graph で照会する。「なぜこのファイルを編集したか」「このファイルを触った全セッションとその理由」「この決定は何が引き起こしたか」を調べたいときに読み、MCP サーバー semantica-trace のツール(decisions_about_file / sessions_touching_file / causal_chain / graph_stats)を呼ぶ。過去セッションを遡って取り込みたいとき、SessionEnd での取り込みを直したいときにも読む。
allowed-tools: mcp__plugin_semantica-trace_semantica-trace__decisions_about_file, mcp__plugin_semantica-trace_semantica-trace__sessions_touching_file, mcp__plugin_semantica-trace_semantica-trace__causal_chain, mcp__plugin_semantica-trace_semantica-trace__graph_stats, Bash(python3:*), Bash(uv:*), Read, Grep, Glob
---

# semantica-trace

`~/.claude/projects/<slug>/<session-id>.jsonl` を読み、`tool_use` を含む assistant ターン
1つを decision ノード1つとして [semantica](https://github.com/semantica-agi/semantica) の
`ContextGraph` に書き込む。Issue #39。

記録はこのライブラリが直接行い、**semantica の MCP サーバー経由では記録しない**。
モデルが記録するかどうかを判断する経路にすると、記録の欠落が起きるうえエージェント
ループも汚れる。

## 前提

隔離 venv が必要。リポジトリには何もインストールしない。

```bash
uv venv ~/.cache/semantica-trace/.venv
uv pip install --python ~/.cache/semantica-trace/.venv/bin/python 'semantica[all]'
# semantica[all] の pinecone 依存が壊れているため差し替える(下の罠を参照)
uv pip uninstall --python ~/.cache/semantica-trace/.venv/bin/python pinecone-client
uv pip install   --python ~/.cache/semantica-trace/.venv/bin/python pinecone
```

グラフバックエンド(Neo4j / Oxigraph)は不要。永続化は
`~/.cache/semantica-trace/data/graph-<YYYY-MM>.json` への JSON 読み書きだけ。
月次シャードに分ける理由は「グラフのシャーディング」節を参照する。

## 使い方

1本の transcript を取り込む。同じセッションを何度呼んでも重複しない。
`--graph-path` を省略すると、セッションの月から自動でシャードを選ぶ。

```bash
cd "${CLAUDE_PLUGIN_ROOT}/skills/semantica-trace"
~/.cache/semantica-trace/.venv/bin/python -m lib.ingest_cli \
  --session-id <session-id> \
  --transcript ~/.claude/projects/-Users-<user>--claude/<session-id>.jsonl \
  --project $HOME/.claude \
  --graph-dir ~/.cache/semantica-trace/data
```

`ingest_session.sh` は SessionEnd フック用の薄いラッパーで、stdin の JSON からパスを
解決して上を呼ぶだけ。

## 過去セッションをまとめて取り込む

```bash
cd "${CLAUDE_PLUGIN_ROOT}/skills/semantica-trace"
~/.cache/semantica-trace/.venv/bin/python -m lib.backfill --dry-run   # 件数だけ見る
~/.cache/semantica-trace/.venv/bin/python -m lib.backfill             # 実行
~/.cache/semantica-trace/.venv/bin/python -m lib.backfill --fresh     # 作り直す
```

`ingest_cli` をループで回してはいけない。あちらは1本ごとにグラフを読んで書き戻すため、
本数に比例して書き戻しが積み上がり IO が O(N^2) になる。`backfill` はシャード1本ごとに
1回読んで1回書く。実測で親 697 本とサブエージェント 348 本を 21 秒で処理する。

`--checkpoint-every` 件ごとに保存し、途中で落ちても進捗を失わない。保存は同じ
ディレクトリの一時ファイルへ書いてから rename する。

## グラフのシャーディング

グラフは月次のシャードファイル `graph-<YYYY-MM>.json` に分けて保存する。シャードキーは
セッションの transcript 内で最初に見つかる timestamp から作り、ファイルの mtime は使わない。
mtime は再取り込みで変わり得るため、同じセッションが取り込みのたびに別のシャードへ
振り分けられてしまう。

サブエージェントの transcript は親と同じ `sessionId` を持つ。実測では CAUSED の辺
44154 本のうちセッションをまたぐものは2本だけで、親子の因果関係はほぼ100%セッション内に
閉じている。そのため親のシャードキーへサブエージェントを揃え、必ず同じシャードへ入れる。
これを守らないと、親子の決定が別シャードに分かれた瞬間に `add_causal_relationship` が
エンドポイント不在で辺を静かに作らなくなる。

シャード分割前は SessionEnd フックが呼ばれるたびに全期間分のグラフを丸ごと読んで
書き戻しており、コストがセッション累計サイズに比例して増え続けていた。シャード分割後は
今月のシャード1本だけを読み書きするため、この累積コストが消える。

`ingest_cli`・`backfill` のどちらも `--graph-path` を明示するとシャーディングを無効にして
単一ファイルへ書く。既存の検証や小規模な動作確認で使う。

照会側の `decisions_about_file`・`sessions_touching_file` はファイルがどの月に触られたか
分からないため、全シャードを読んで結果をマージする。`causal_chain` は因果関係がほぼ
セッション内に閉じる実測を利用して、対象の decision_id を含むシャード1本だけを読む。
`mcp_server.py` はシャードごとに読み込み結果をキャッシュし、mtime が変わったシャードだけ
読み直す。SessionEnd が触るのは基本的に今月のシャード1本だけなので、他の月のキャッシュは
触れる限り再利用され続ける。これは SessionEnd が1回に読み書きする IO 量を減らす仕組みで
あり、`mcp_server.py` プロセスが常駐している間に保持し続ける総メモリ量を減らす仕組みでは
ない。一度でも全シャードへ触るクエリ(`graph_stats` 等)を呼ぶと、単一グラフ時代と同じ
総量のグラフがプロセスのメモリに載る。

エンティティノードはシャードごとに独立している。同じファイルを指す Entity ノードが
複数のシャードに重複して存在し得るため、`graph_stats` が返す node_count はシャード間の
重複を含んだ単純合計になる。

同じ月のシャードへ複数の SessionEnd が同時に書き込んだ場合、後勝ちで一方の更新が
失われ得る。`save_graph` の原子的な rename は書き込み途中のファイル破損を防ぐだけで、
並行更新の欠落までは防がない。シャーディングはこの制限を解決しない。

既存グラフをシャード構成へ移行するときは、`backfill --fresh` を再実行する。
decision_id はセッションIDとメッセージUUIDから決まる安定した値なので、
transcript から再取り込みしても同じグラフに帰着する。

## サブエージェントの決定

サブエージェントの transcript は `<親セッションID>/subagents/agent-<agentId>.jsonl` に
置かれ、中身は全レコードが `isSidechain: true` である。**`parse_transcript` はこれを
1件も返さない**ため、`parse_subagent_transcript` で別に読む。`backfill` は親とサブを
分けて探索し、両方を取り込む。

実測では取り込み対象 1056 本のうち 362 本がこの形で、1本あたり 20〜40 件の tool_use を
含んでいた。取り込まないとサブエージェントに委譲した作業の「なぜ」が丸ごと欠ける
(実測で decision の 17.6% がここに属する)。

親子は tool_result に入る `agentId` で繋ぐ。**レコード直下の構造化フィールド
`toolUseResult.agentId` を主に使う**(実測 349 件)。本文テキストへの正規表現だけに頼ると、
テキストに `agentId:` が現れない形式を取り落とし、実測で 79 本が親へ繋がらなかった。
テキストはフォールバックに留め、当てるときは切り詰める前の全文に対して行う
(`outcome` は 800 文字で切るため、切った後に探すと取り落とす)。

**ツール名でゲートしてはいけない。** エージェントの起動は `Agent`/`Task` 以外にも `Skill`
経由で起こる(実測 18 件)。`ENTITY_AGENT_TOOLS` で先に弾くと、その分の親子関係が丸ごと
落ちる。agentId が付いている tool_result はすべて起動として扱う。

**agentId の収集は親だけでなく全サブエージェント transcript も走査する
(`collect_spawned_agent_ids`、`backfill.py` で親+サブ両方に対して呼ぶ)。** 理由は2つ。

1. サブエージェントが**さらに別のサブエージェントを起動する(nested)** 場合、起動の記録は
   サブエージェント自身の transcript の中にあり、トップレベルの親には一切現れない
   (実測: #44 で見つかった未リンク13本のうち6本がこれだった)
2. バックグラウンドの slash コマンド起動(`/code-review low --fix 3,4,9` 等)は
   `Agent`/`Task`/`Skill` の tool_use を経由せず、`type: "system", subtype:
   "local_command"` レコードの `content` に
   `<forked-skill-launch>{"agentId": ...}</forked-skill-launch>` というマーカーで
   直接 agentId を埋め込む(実測1件)。tool_use を起点に探すロジックでは見つからない

この2つを合わせて、未リンクは 79 本 → 13 本 → **5 本**まで減った。残る5本は
**構造的に直せない**: `Agent`/`Task` を**同期呼び出し**(`run_in_background: false`)した
場合、`toolUseResult` は `{"status": "completed", "prompt": ...}` のみで、
**`agentId` キー自体が最初から存在しない**(非同期呼び出しだけが `isAsync: true` と
`agentId` を持つ)。サブエージェント側の transcript ファイルは同期呼び出しでも作られるが、
親側にそれを指す手がかりが一切残らない。抽出ロジックの改善では埋められない。

サブエージェントの最初の決定だけを起動元へ `CAUSED` で繋ぎ、2件目以降はファイル内の
`parentUuid` に任せる。

**サブエージェント transcript の根の `isMeta` レコードは捨ててはいけない。** 親セッションでは
`isMeta` はシステムの注入物なので境界にも理由にもしないが(下の罠を参照)、サブエージェント
ファイルの先頭にある `isMeta` レコードは**親からの委任指示そのもの**である。実測 363 本のうち
19 本がこの形で、捨てるとそのファイルの全ターンの理由が空になる。`_is_sidechain_root()` で
この2つを区別している。

`sessionId` はサブエージェント側でも**親のセッションID**が入っている。`decision_id` は
`<session_id>:<message_uuid>` のままで、uuid が一意なので親のターンと衝突しない。
metadata の `agent_id` と `is_sidechain` で親子を区別する。

## 照会する

**照会は MCP サーバー `semantica-trace` のツールを呼ぶ。** サーバーはこのプラグインの
`.mcp.json` から登録されるため、手動での `claude mcp add` は不要である。起動は
`run-mcp.sh` が隔離 venv の python を解決して行う。venv の場所を変える場合は
`SEMANTICA_TRACE_PYTHON` で上書きする。

| ツール | 返すもの |
|---|---|
| `mcp__plugin_semantica-trace_semantica-trace__decisions_about_file` | そのファイルを「なぜ触ったか」を全セッション横断で時系列に。`reasoning` が理由、`rationale_source` がその出どころ、`rationale_distance` が大きいほど理由が遠い |
| `mcp__plugin_semantica-trace_semantica-trace__sessions_touching_file` | そのファイルを触ったセッション ID の一覧。どのセッションを読み返すか当たりをつける |
| `mcp__plugin_semantica-trace_semantica-trace__causal_chain` | ある決定の因果チェーン。`direction` は `upstream`(何が引き起こしたか)か `downstream` |
| `mcp__plugin_semantica-trace_semantica-trace__graph_stats` | グラフの規模と取り込み済みセッション数。**照会結果が空だったとき、グラフが空なのか条件が外れたのかを切り分けるために先に呼ぶ** |

典型的な流れは `decisions_about_file` でファイルの履歴を見て、気になる決定の
`decision_id` を `causal_chain` に渡して上流を辿る。

**このサーバーは読むだけで、書き込む手段を持たない。** 記録は SessionEnd フックだけが行う。
モデルに記録させると、記録するかどうかがモデルの判断次第になって欠落が起き、
エージェントループも汚れる。

Python から直接使う場合は `lib/query.py` の `decisions_about_file` /
`sessions_touching_file` / `causal_chain` を呼ぶ。MCP サーバーはこの3関数の薄い
ラッパーである。

## モジュール

| ファイル | 役割 |
|---|---|
| `lib/transcript_parser.py` | JSONL → `Turn` のリスト。`parentUuid` を辿って rationale と因果の親を特定し、file/command/agent_type をエンティティとして抽出する |
| `lib/graph_ingest.py` | `Turn` → `ContextGraph` への冪等な書き込み |
| `lib/query.py` | セッション横断クエリ |
| `lib/ingest_cli.py` | CLI エントリポイント。失敗を握り潰して exit 0 |
| `ingest_session.sh` | SessionEnd フック用の薄いラッパー |
| `mcp_server.py` | 照会専用の stdio MCP サーバー。`lib/query.py` を包むだけ |
| `NOTES.md` | 実 API の調査ノート。実測と推測を区別して書いてある |

## テストを実行する

```bash
cd "${CLAUDE_PLUGIN_ROOT}/skills/semantica-trace"
~/.cache/semantica-trace/.venv/bin/python -m pytest tests/
```

実 transcript を要するテストは既定で skip する。transcript には実際の会話内容が
入るため、CI にチェックインできる形にすると「機微情報」の方針に反する。ローカルで
実データを使って検査する場合だけ `--transcript`/`--subagent-transcript` を渡す。

```bash
~/.cache/semantica-trace/.venv/bin/python -m pytest tests/ \
  --transcript ~/.claude/projects/<slug>/<session-id>.jsonl \
  --subagent-transcript ~/.claude/projects/<slug>/<session-id>/subagents/agent-<id>.jsonl
```

被覆率やノード数のような transcript 依存の数値は assert しない。壊れると
黙って誤答する性質(注入物が理由に混ざる・agentId の抽出が壊れる等)だけを固定する。

## 実測で分かった罠

`semantica[all]` は素の状態では import できない。固定されている `pinecone-client==6.0.0` が
`import pinecone` の時点で「パッケージ名が `pinecone` に変わった」という例外を投げるように
作られており、`semantica.context.__init__` から `pinecone_store.py` までの import 連鎖が
遅延ではなく無条件に走るため、`from semantica.context import ContextGraph` が必ず失敗する。
`pinecone-client` を消して `pinecone` を入れると通る。

**`semantica` の CLI (`semantica decision record/list/trace`) は使えない。** `semantica doctor` は
"Graph store ✓ memory (always available)" と報告するが、CLI が内部で使う `GraphStore` クラスは
neo4j / falkordb / neptune / age の4バックエンドしか持たず `memory` 分岐が存在しないため、
既定で Neo4j へ接続を試みて失敗する。doctor が言う memory は別系統の
`semantica.context.ContextGraph` を指している。Python API を直接呼ぶ。

**因果エッジに `DecisionRecorder.link_precedents()` を使わない。** `relationship_type` が
`similar_scenario` / `same_policy` / `exception_precedent` の enum に縛られており、
「同一セッションの前ターン」を表現できない。`ContextGraph.add_causal_relationship()`
(`CAUSED` / `INFLUENCED` / `PRECEDENT_FOR`)を使う。両端が `node_type == "Decision"` でないと
例外を投げずに黙って何もしないので、渡す ID を間違えても気づけない。

**ノードは冪等だがエッジは冪等でない。** `add_node` は `nodes[node_id] = node` の辞書代入なので
同じ ID の再投入は上書きで済むが、`add_edge` は `edge_id` を決定的ハッシュで計算しておきながら
`_add_internal_edge()` が重複チェックなしで append するため、同じエッジが2件入る。
`graph_ingest.py` の `_edge_exists()` が追加前に照会して吸収している。ここを外すと
再 ingest でエッジが増殖する。

**エンティティ ID は `md5(f"{text}_{type}")` の完全一致方式**で、類似度による誤統合は起きない。
ただし相対パスと絶対パスを混ぜると同一ファイルが別エンティティに分裂するため、呼び出し側で
絶対パス化と `normpath` をかける必要がある。

**この環境の transcript に thinking の可視テキストが残っていない。** `thinking` フィールドは
すべて空文字列で `signature` だけがある(大きい6本で417個中0個、ランダム40本で736個中0個が非空)。
そのため rationale は `parentUuid` を遡って探す。

**祖先探索をホップ数で打ち切ってはいけない。** 打ち切り上限がそのまま理由の被覆率になる
(実測: 上限6で49.7%、12で68.2%、20で80.6%、40で91.4%、無制限で94.4%)。tool_use を含む
assistant ターンは `[text, tool_use]` のように text と同居することが一度もなく(実測1064ターン中0件、
並列 tool_use も0件)、理由は必ず別の text 専用ターンにあるため、ツール呼び出しが連続すると
1回ごとに2ホップ遠ざかる。上限6は「3回前のツール呼び出しまで」を意味していた。

代わりに **直近の本物のユーザープロンプトを境界にして止める**。境界を越えた text は別タスクの
理由だからである(実測で境界越えは4.6%)。境界に先に到達した場合はそのプロンプト自体を理由に
使い、`rationale_source = "user_prompt"` を立てる。解決順は
`thinking`(あれば優先) → `text` → `user_prompt` → `none`。

**実測の被覆率: 非空の理由 100%**(大きい6本、1076 turn。text 89.9% / user_prompt 10.1% / none 0%)。
理由テキストまでの距離を `rationale_distance`(挟まっていた decision の数)として metadata に
残してあり、距離2以内が65.5%、最大37。遠い理由を弱いものとして絞り込むのは照会側の判断にできる。

**ユーザーメッセージには人間が書いていない注入物が混ざる。** 実測67件の本物のプロンプトのうち
slash コマンドの記録15件、`Caveat:` 9件、`<local-command-stdout>` 12件、`<system-reminder>` 1件、
`UserPromptSubmit` の追加コンテキスト2件。落とさずに理由として引用すると git status のダンプが
理由になる。`_NOISE_PATTERNS` で除去し、除去後に本文が空になる記録(slash コマンド単体など)は
「境界としては数えるが理由には使わない」扱いにしている。

## 運用上の注意

グラフは1ファイルの JSON で、ingest ごとに全体を読んで全体を書き戻す。セッションが
積み上がると1回の ingest のコストがグラフ全体のサイズに比例して伸びる。411 turn の
セッション1本で 1.1MB になっており、**分割か定期的な切り出しが必要になる時期が来る**。
`--graph-path` を月単位などで分ける運用が現実的。

**グラフの保存(`graph_ingest.save_graph()`)は原子的。** `ContextGraph.save_to_file()` は
指定パスへ直接書き込むため、これをそのまま SessionEnd フックや backfill から呼ぶと、
書き込み中にプロセスが落ちた(タイムアウト・スリープ・kill)場合にグラフが丸ごと壊れる。
同じディレクトリの一時ファイルへ書いてから `rename` する形にしてある。**この関数を経由
せずに `graph.save_to_file()` を直接呼ばないこと**(#42 のレビューで backfill.py 側にだけ
この対策が入り、SessionEnd フックが実際に通る `ingest_cli.py` の経路は素通しのままだった。
#45 で気付いて統一した)。

**`ingest_cli.py`/`backfill.py` の終了は `os._exit()` を使う。** faiss の macOS wheel は
`libomp.dylib` を自前で同梱しており、Python の通常のインタプリタ終了処理(atexit・静的
デストラクタ)と衝突して、保存が完全に終わった後に非決定的に
`libc++abi: recursive_mutex lock failed` で落ちることがある(実測: 同一の `--fresh`
実行を数回繰り返して1回だけ発生。データへの影響はない。グラフ・一時ファイルとも無傷)。
`raise SystemExit(main())` や `sys.exit(main())` だと通常の終了処理を経由してこの
クラッシュを踏む可能性が残るため、`main()` の戻り値で `os._exit()` する。標準出力・
標準エラーを flush してから呼ぶこと(`os._exit()` はバッファのフラッシュもしない)。

## 機微情報

transcript にはコマンド出力経由のトークン・env ダンプ・ファイル内容が入り、`outcome` として
グラフにも複製される。`~/.cache/semantica-trace/data/` は 700、各シャードファイルは 600 にする。
**semantica のサーバーを立てる場合は localhost バインドに限定し、ホスティング先に向けない。**

## MCP サーバーの罠

**semantica 同梱の `semantica mcp start` は使わない。** `python -m mcp.server` を呼ぶだけで
`semantica.mcp_server` の実ハンドラーと配線されていない。自前の `mcp_server.py` を使う。

一方で **PyPI の `mcp` は公式 SDK である**(2.0.0、repo は `modelcontextprotocol/python-sdk`、
publisher は Model Context Protocol a Series of LF Projects, LLC)。`httpx2` や `mcp-types` は
公式 v2 の正規の依存であり、見慣れないからといって別物ではない。

**API は 1.x と違う。** `mcp.server.fastmcp.FastMCP` は存在せず、
`mcp.server.mcpserver.MCPServer` を使う。デコレータは `@server.tool(description=...)`、
起動は `server.run(transport="stdio")`。

**起動時に semantica を import してはいけない。** import に実測 5.6 秒かかり、stdio の MCP
サーバーはセッション開始ごとに起動されるため、全セッションがその 5.6 秒を払うことになる。
`mcp_server.py` は semantica の import とグラフ読み込みを最初のツール呼び出しまで遅延させて
おり、モジュールの import は 0.45 秒で終わる(実測)。ツール関数の中で `from lib.query import ...`
しているのはこのためで、トップレベルに上げると起動が重くなる。

**stdout を汚してはいけない。** stdio トランスポートは stdout が JSON-RPC 専用のため、
print が1行混ざるとプロトコルが壊れる。semantica のログと faiss のロードメッセージは
stderr に出ることを実測で確認済み(stdout は空)。ログ出力を stdout に向ける変更を入れないこと。

**ファイルパスは MCP の入口で絶対パス化している。** エンティティ ID は絶対パス文字列の
md5 なので、相対パスをそのまま照会すると ID が一致せず必ず 0 件になる。0 件は
「そのファイルは触っていない」と読めてしまい、黙って間違った結論を出す。`_resolve()` で
`expanduser` + `abspath` + `normpath` をかけてから照会する。

**`ContextGraph` の統計は `stats()`。** `get_statistics()` は存在しない。`hasattr` で
逃げる書き方にすると、黙って空 dict を返して「グラフが空」と誤読させる。

## 未完了

- 取り込みと照会の実装は完了している。有効化はプラグインのインストールで済み、
  環境ごとに残る作業は隔離 venv の作成だけである
## SessionEnd への登録

取り込みはこのプラグインの `hooks/hooks.json` が SessionEnd に登録する。利用者側の
`settings.json` を編集する必要はない。sui-memory のフックと並べても、両方が同一
セッションで発火することを実測で確認してある。

### 実測で確かめた発火の挙動

隔離したディレクトリに `.claude/settings.json` だけを置いて `claude -p` を回し、
グローバル設定を触らずに確認した結果を残す。

- **SessionEnd は発火する。** フックが同期的に呼ばれ、stdin に JSON が届く
- **`nohup ... &` の子プロセスは生き残る。** フック本体が exit した後に書き込みが
  完了することを確認した。セッション終了をブロックしないためこの形を使う
- **stdin は `transcript_path` を直接くれる。** `session_id` と `cwd` からスラッグを
  組み立てる必要はない。`ingest_session.sh` は `transcript_path` を優先し、
  無い場合だけ cwd から組み立てる
- end-to-end で decision ノードと entity ノードがグラフに増えることを確認した
  (グローバル設定からの発火も、プロジェクト設定を持たないディレクトリで確認済み)
- **プロジェクト設定の `SessionEnd` はユーザー設定のものを置き換えず、両方が走る**
  (probe と sui-memory の両方が同時に発火した)

`sui-memory/ingest.log` のように**ログの更新が止まっていても、フックが壊れている
とは限らない**。SessionEnd はクリーンに終了したセッションでしか発火しないため、
強制終了やクラッシュが続くと更新が止まる。ログの日付だけを見て壊れたと判断しない。

