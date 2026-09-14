"""過去セッションをまとめてグラフへ取り込む。

``ingest_cli`` は1セッションごとにグラフを読んで書き戻す。SessionEnd から1回
呼ばれる用途ではそれでよいが、過去の全セッションに対して繰り返すと書き戻しが
セッション数に比例して積み上がり、IO が O(N^2) になる。こちらは対象セッションを
月次シャード(``graph-<YYYY-MM>.json``)へ振り分け、シャードごとに1回だけ
読んで全セッションをメモリ上で取り込んでから書く(#43)。

シャードキーはセッションの transcript 内で最初に見つかる timestamp から作る。
ファイルの mtime は再取り込みで変わり得るため使わない。サブエージェントの
transcript は親と同じ ``sessionId`` を持つ(実測: 44154 本の CAUSED 辺のうち
セッションをまたぐものは2本のみ)ため、親のシャードキーへ揃えて同じシャードに
入れる。そうしないと親子の因果関係の辺が別シャードをまたぎ、
``add_causal_relationship`` がエンドポイント不在で静かに何もしなくなる。

途中で落ちても進捗を失わないよう、シャードごとに ``--checkpoint-every`` 件ごとに
保存する。保存の原子性は ``graph_ingest.save_graph()`` が持つ(一時ファイル
経由の rename)。

``--graph-path`` を明示すると、シャーディングを無効にして単一ファイルへ書く
旧来のモードに戻る(既存テスト・小規模な検証用)。

使い方:
    python -m lib.backfill                      # ~/.claude/projects 配下すべて
    python -m lib.backfill --projects-dir DIR   # 別の場所
    python -m lib.backfill --dry-run            # 対象の件数だけ見る
    python -m lib.backfill --graph-path PATH    # シャーディング無効、単一ファイル

制限: SessionEnd フック同士の並行書き込みは ingest_cli.py が shard_lock で
直列化するため lost update は起きない。ただし backfill 自身はこのロックを
取らないため、backfill 実行中に SessionEnd フックが同じ月のシャードへ書き込むと、
後勝ちで一方の更新が失われ得る(save_graph の原子的 rename は破損を防ぐだけで、
並行更新の欠落までは防がない)。
"""

from __future__ import annotations

import argparse
import glob
import os
import sys
import time
from typing import List

from collections import defaultdict

from semantica.context import ContextGraph

from .graph_ingest import (
    DEFAULT_GRAPH_DIR,
    ingest_turns,
    list_shard_paths,
    save_graph,
    shard_key_for_timestamp,
    shard_path,
)
from .transcript_parser import (
    collect_spawned_agent_ids,
    parse_subagent_transcript,
    parse_transcript,
    session_id_and_first_timestamp,
)

# 1KB 未満の transcript は decision が立たない(SessionEnd フックと同じ閾値)
MIN_SIZE_BYTES = 1024


def _big_enough(path: str) -> bool:
    return os.path.getsize(path) >= MIN_SIZE_BYTES


def find_transcripts(projects_dir: str) -> List[str]:
    """親セッションの transcript。サブエージェントのものは含めない。"""
    pattern = os.path.join(projects_dir, "**", "*.jsonl")
    found = glob.glob(pattern, recursive=True)
    return sorted(
        f
        for f in found
        if _big_enough(f) and os.path.basename(os.path.dirname(f)) != "subagents"
    )


def find_subagent_transcripts(projects_dir: str) -> List[str]:
    """サブエージェントの transcript。

    ``<親セッションID>/subagents/agent-<agentId>.jsonl`` に置かれる。中身は全て
    ``isSidechain: true`` なので、親と同じ経路では1件も取り込まれない。
    """
    pattern = os.path.join(projects_dir, "**", "subagents", "*.jsonl")
    return sorted(f for f in glob.glob(pattern, recursive=True) if _big_enough(f))


def _ingest_group(
    graph_path: str,
    fresh: bool,
    parent_paths: List[str],
    subagent_paths: List[str],
    causal_parent_by_agent: dict,
    checkpoint_every: int,
    label: str,
) -> tuple:
    """1シャード分の transcript を1つのグラフへ取り込んで保存する。

    シャードごとに ContextGraph を作って捨てるので、ピークメモリはシャード
    1本分に収まる(単一グラフだった頃は全セッション分が常にメモリに載っていた)。
    """
    graph = ContextGraph(advanced_analytics=False)
    if not fresh and os.path.exists(graph_path):
        graph.load_from_file(graph_path)
        print(
            f"[{label}] 既存シャードを読み込んだ: {graph.stats()['node_count']} nodes",
            file=sys.stderr,
        )

    ok = 0
    failed: List[tuple] = []
    turns_total = 0

    for index, path in enumerate(parent_paths, start=1):
        session_id = os.path.splitext(os.path.basename(path))[0]
        try:
            turns = parse_transcript(path, session_id=session_id)
            if turns:
                ingest_turns(graph, turns)
                turns_total += len(turns)
            ok += 1
        except Exception as exc:  # 1本の破損で全体を止めない
            failed.append((path, f"{type(exc).__name__}: {exc}"))
        if index % checkpoint_every == 0:
            save_graph(graph, graph_path)
            print(
                f"[{label} {index}/{len(parent_paths)}] checkpoint "
                f"turns={turns_total} nodes={graph.stats()['node_count']}",
                file=sys.stderr,
            )

    sub_ok = 0
    sub_linked = 0
    for index, path in enumerate(subagent_paths, start=1):
        try:
            turns = parse_subagent_transcript(path, causal_parent_by_agent)
            if turns:
                if turns[0].causal_parent_decision_id:
                    sub_linked += 1
                ingest_turns(graph, turns)
                turns_total += len(turns)
            sub_ok += 1
        except Exception as exc:
            failed.append((path, f"{type(exc).__name__}: {exc}"))
        if index % checkpoint_every == 0:
            save_graph(graph, graph_path)

    save_graph(graph, graph_path)
    stats = graph.stats()
    print(
        f"[{label}] 完了: {ok}/{len(parent_paths)} 本 + サブエージェント "
        f"{sub_ok}/{len(subagent_paths)} 本(起動元へ繋がった {sub_linked} 本), "
        f"turns={turns_total}, nodes={stats['node_count']}, edges={stats['edge_count']}",
        file=sys.stderr,
    )
    return ok, sub_ok, sub_linked, turns_total, failed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--projects-dir", default=os.path.expanduser("~/.claude/projects")
    )
    parser.add_argument(
        "--graph-path",
        default=None,
        help="明示すると単一ファイルへ書く(シャーディング無効、旧来の互換モード)",
    )
    parser.add_argument("--graph-dir", default=DEFAULT_GRAPH_DIR)
    parser.add_argument("--checkpoint-every", type=int, default=200)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="既存グラフを読まずに作り直す。decision_id は安定なので"
        "読み込んでも重複しないが、スキーマを変えたときに使う",
    )
    args = parser.parse_args()

    transcripts = find_transcripts(args.projects_dir)
    subagents = find_subagent_transcripts(args.projects_dir)
    print(f"対象 transcript: {len(transcripts)} 本", file=sys.stderr)
    if args.dry_run:
        total = sum(os.path.getsize(f) for f in transcripts)
        print(f"合計 {total / 1e6:.0f}MB", file=sys.stderr)
        return 0

    started = time.time()

    # agentId -> 起動した側の decision_id。親からの起動だけでなく、サブエージェントが
    # さらに別のサブエージェントを起動する(nested)場合や、Agent/Task/Skill の
    # tool_use を経由しないバックグラウンド slash コマンド起動(forked-skill-launch)も
    # 拾うため、親とサブエージェントの**両方**の transcript を走査してから
    # ingest する。#44 で判明した「未リンク13本」のうち、nested な6本と
    # forked-skill-launch の1本はこの収集を親だけに限っていたのが原因だった
    # (残り約6本は Agent/Task の同期呼び出し(run_in_background: false)で、
    # 親の tool_result に agentId 自体が一切書かれない。extraction では
    # 直せない構造的な欠落)。
    causal_parent_by_agent = {}
    for path in transcripts + subagents:
        try:
            causal_parent_by_agent.update(collect_spawned_agent_ids(path))
        except Exception:
            pass  # 収集の失敗は ingest 側で再度検出されるので、ここでは黙って進む
    print(
        f"サブエージェント transcript: {len(subagents)} 本 "
        f"(起動元を辿れる agentId: {len(causal_parent_by_agent)} 件)",
        file=sys.stderr,
    )

    if args.graph_path:
        # 旧来の単一ファイルモード。シャーディングを完全に迂回する。
        ok, sub_ok, sub_linked, turns_total, failed = _ingest_group(
            args.graph_path,
            args.fresh,
            transcripts,
            subagents,
            causal_parent_by_agent,
            args.checkpoint_every,
            label="single",
        )
    else:
        # セッションごとにシャードキー(YYYY-MM)を決める。サブエージェントは
        # 親と同じ session_id を持つ(docstring 参照)ので、親のシャードキーへ
        # 揃える。親 transcript が見つからない孤立したサブエージェントだけ、
        # 自身の timestamp から独自にシャードキーを決める。
        session_shard: dict = {}
        parents_by_shard: dict = defaultdict(list)
        for path in transcripts:
            session_id, timestamp = session_id_and_first_timestamp(path)
            shard_key = shard_key_for_timestamp(timestamp, fallback_path=path)
            session_shard[session_id] = shard_key
            parents_by_shard[shard_key].append(path)

        subagents_by_shard: dict = defaultdict(list)
        for path in subagents:
            session_id, timestamp = session_id_and_first_timestamp(path)
            shard_key = session_shard.get(session_id)
            if shard_key is None:
                shard_key = shard_key_for_timestamp(timestamp, fallback_path=path)
            subagents_by_shard[shard_key].append(path)

        shard_keys = sorted(set(parents_by_shard) | set(subagents_by_shard))
        print(f"シャード数: {len(shard_keys)} ({', '.join(shard_keys)})", file=sys.stderr)

        if args.fresh:
            # 今回のスキャンで見つかった月だけを作り直すと、transcript が
            # ローテーション・削除されて消えた過去の月のシャードは対象外になり、
            # --fresh を何度実行しても永久に残り続けてしまう(実測で確認)。
            # 単一ファイル時代の --fresh(全体を作り直す)と同じ保証にするため、
            # 既存のシャードを先に全て消してから作り直す。
            for stale_path in list_shard_paths(args.graph_dir):
                os.remove(stale_path)
                print(f"[fresh] 既存シャードを削除: {os.path.basename(stale_path)}", file=sys.stderr)

        ok = sub_ok = sub_linked = turns_total = 0
        failed = []
        for shard_key in shard_keys:
            r_ok, r_sub_ok, r_sub_linked, r_turns, r_failed = _ingest_group(
                shard_path(shard_key, args.graph_dir),
                args.fresh,
                parents_by_shard.get(shard_key, []),
                subagents_by_shard.get(shard_key, []),
                causal_parent_by_agent,
                args.checkpoint_every,
                label=shard_key,
            )
            ok += r_ok
            sub_ok += r_sub_ok
            sub_linked += r_sub_linked
            turns_total += r_turns
            failed.extend(r_failed)

    elapsed = time.time() - started
    print(
        f"完了: {ok}/{len(transcripts)} 本, サブエージェント {sub_ok}/{len(subagents)} 本"
        f"(起動元へ繋がった {sub_linked} 本), turns={turns_total}, {elapsed:.0f}s",
        file=sys.stderr,
    )
    if failed:
        print(f"失敗 {len(failed)} 本:", file=sys.stderr)
        for path, reason in failed[:20]:
            print(f"  {os.path.basename(path)}: {reason}", file=sys.stderr)
        if len(failed) > 20:
            print(f"  ... 他 {len(failed) - 20} 本", file=sys.stderr)
    return 0


if __name__ == "__main__":
    # faiss の macOS wheel が同梱する libomp と Python のインタプリタ終了処理が
    # 衝突し、保存が完全に終わった後に非決定的な libc++abi クラッシュが起きる
    # ことがある(実測: 同一の --fresh 実行を数回繰り返して1回だけ発生。データ
    # への影響はない)。sys.exit() は通常の終了処理を経由してこのクラッシュを
    # 踏む可能性が残るため、os._exit() で回避する。
    _code = main()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(_code)
