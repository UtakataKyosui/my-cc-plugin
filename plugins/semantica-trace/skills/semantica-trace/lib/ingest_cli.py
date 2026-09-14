"""CLI entrypoint used by ingest_session.sh (SessionEnd hook wrapper).

Usage:
  <venv>/bin/python -m lib.ingest_cli --session-id <id> --transcript <path> [--project <cwd>]

Idempotent: safe to call repeatedly for the same transcript (see NOTES.md #5
and tests/test_idempotency.py). Never raises on expected "nothing to do"
conditions (missing/short transcript) — mirrors session-end-ingest.sh's
failure-swallowing convention so the SessionEnd hook is never the reason a
session fails to close.
"""

from __future__ import annotations

import argparse
import os
import sys

# faiss の macOS wheel は libomp を自前で同梱しており、Python の通常の
# インタプリタ終了処理(atexit・静的デストラクタ)と衝突して、既に全ての
# 出力・保存が終わった後に非決定的に `libc++abi: recursive_mutex lock
# failed` で落ちることがある(実測: 同一の --fresh 実行を4回繰り返して
# 1回だけ発生。faiss 自身が macOS wheel に libomp.dylib を同梱しているのが
# 原因で、semantica.context の import 時点で必ず faiss が読み込まれる)。
# グラフの保存は save_graph() の時点で同期的に完了しており、この後に何が
# 起きてもデータへの影響はない。os._exit() は atexit・GC・静的デストラクタを
# 一切走らせない生の終了なので、この既知のクラッシュ経路を丸ごと避けられる。

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from lib.graph_ingest import (  # noqa: E402
    DEFAULT_GRAPH_DIR,
    ingest_turns,
    load_or_create_graph,
    save_graph,
    shard_key_for_timestamp,
    shard_lock,
    shard_path,
)
from lib.transcript_parser import parse_transcript, session_id_and_first_timestamp  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--transcript", required=True)
    parser.add_argument("--project", default=None)
    parser.add_argument(
        "--graph-path",
        default=None,
        help="明示すると単一ファイルへ書く(既存テスト・後方互換用)。"
        "省略時はセッションの月から自動でシャード(--graph-dir 配下の"
        "graph-<YYYY-MM>.json)を選ぶ",
    )
    parser.add_argument("--graph-dir", default=DEFAULT_GRAPH_DIR)
    args = parser.parse_args()

    if not os.path.isfile(args.transcript):
        print(f"skip: transcript not found: {args.transcript}")
        return 0

    turns = parse_transcript(args.transcript, session_id=args.session_id)
    if not turns:
        print(f"skip: no tool-use turns in {args.transcript}")
        return 0

    if args.graph_path:
        graph_path = args.graph_path
    else:
        _, timestamp = session_id_and_first_timestamp(args.transcript)
        shard_key = shard_key_for_timestamp(timestamp, fallback_path=args.transcript)
        graph_path = shard_path(shard_key, args.graph_dir)

    # SessionEnd フックの本体コスト: このセッション1本分の decision(数十〜数百件)
    # を足すためだけに、シャード1本(月次、~数十MB)を読んで書き戻す。単一の
    # 全期間グラフだった頃は、ここが「全セッション累計サイズに比例する」IO に
    # なっていた(#43)。
    #
    # 同じ月に終了した複数セッションが並行してこの read-modify-write に入ると、
    # 後に save した方が先に save した方の decision を消してしまう(lost update)。
    # shard_lock で load から save までを直列化する。
    with shard_lock(graph_path):
        graph = load_or_create_graph(graph_path)
        stats = ingest_turns(graph, turns, source_documents=[args.project or args.session_id])
        save_graph(graph, graph_path)

    print(
        f"ingested session={args.session_id} turns={len(turns)} "
        f"decisions={stats['decisions']} entities_linked={stats['entities_linked']} "
        f"causal_edges_added={stats['causal_edges_added']} "
        f"causal_edges_skipped={stats['causal_edges_skipped']} "
        f"graph_path={graph_path}"
    )
    return 0


if __name__ == "__main__":
    _code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(_code)
