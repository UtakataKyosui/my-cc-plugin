"""Idempotently write parsed transcript Turns into a semantica ContextGraph.

Requires the isolated venv at ``~/.cache/semantica-trace/.venv`` (see
../NOTES.md #0 for why: semantica[all]'s pinecone dependency is broken and
needs a manual swap before ``semantica.context`` becomes importable).

Node-level idempotency comes for free from ContextGraph (dict keyed by
node_id, see NOTES.md #5). Edge-level idempotency does NOT — ContextGraph.
add_edge() blindly appends even when an identical edge already exists — so
this module checks ``_edge_exists()`` before every add_edge /
add_causal_relationship call.
"""

from __future__ import annotations

import glob
import os
import re
import time
from typing import Iterable, List, Optional

from semantica.context import ContextGraph, Decision, DecisionRecorder

from .transcript_parser import Turn

DEFAULT_GRAPH_PATH = os.path.expanduser("~/.cache/semantica-trace/data/graph.json")
DEFAULT_GRAPH_DIR = os.path.expanduser("~/.cache/semantica-trace/data")
SHARD_PREFIX = "graph-"
SHARD_SUFFIX = ".json"
# YYYY-MM だけを厳密に受け付ける。緩い glob (graph-*.json) だと、手作業の
# バックアップ(graph-2026-08.bak.json 等)や一時退避ファイルもシャードとして
# 拾ってしまい、decisions_about_file_multi 等が重複行を返す(#43 レビューで実測)。
_SHARD_FILENAME_RE = re.compile(r"^graph-\d{4}-\d{2}\.json$")


def shard_key_for_timestamp(timestamp: Optional[str], fallback_path: Optional[str] = None) -> str:
    """ISO8601 タイムスタンプから月次シャードキー(YYYY-MM)を作る。

    timestamp が取れない場合(実測ではまず起きないが、破損 transcript を
    想定して防御的に)、fallback_path のファイル mtime を使う。mtime は
    再取り込みで変わり得るため、あくまで最後の手段。
    """
    if timestamp:
        return timestamp[:7]
    if fallback_path and os.path.exists(fallback_path):
        return time.strftime("%Y-%m", time.gmtime(os.path.getmtime(fallback_path)))
    return time.strftime("%Y-%m", time.gmtime())


def shard_path(shard_key: str, graph_dir: str = DEFAULT_GRAPH_DIR) -> str:
    return os.path.join(graph_dir, f"{SHARD_PREFIX}{shard_key}{SHARD_SUFFIX}")


def list_shard_paths(graph_dir: str = DEFAULT_GRAPH_DIR) -> List[str]:
    """graph-<YYYY-MM>.json 形式に厳密に一致するファイルだけを返す。

    緩い glob だとバックアップ・一時退避ファイル(例: graph-2026-08.bak.json)も
    シャードとして拾ってしまい、横断クエリが同じ内容を重複して返す。
    """
    candidates = glob.glob(os.path.join(graph_dir, f"{SHARD_PREFIX}*{SHARD_SUFFIX}"))
    return sorted(
        p for p in candidates if _SHARD_FILENAME_RE.match(os.path.basename(p))
    )


def has_legacy_single_graph(graph_dir: str = DEFAULT_GRAPH_DIR) -> Optional[str]:
    """シャーディング以前の単一ファイル(graph.json)がまだ残っているか調べる。

    シャード分割後にこのファイルが放置されると、list_shard_paths からは
    見えないため、backfill --fresh でシャードへ移行するまで全クエリが
    「グラフが無い」を返す(実測: マージ直後にこの状態を再現した)。
    """
    legacy = os.path.join(graph_dir, "graph.json")
    return legacy if os.path.exists(legacy) else None


def load_or_create_graph(graph_path: str = DEFAULT_GRAPH_PATH) -> ContextGraph:
    graph = ContextGraph(advanced_analytics=False)
    if os.path.exists(graph_path):
        graph.load_from_file(graph_path)
    return graph


def save_graph(graph: ContextGraph, graph_path: str = DEFAULT_GRAPH_PATH) -> None:
    """グラフを原子的に保存する。

    ``ContextGraph.save_to_file()`` は指定パスへ直接書き込む(``open(path, "w")``)。
    グラフは1ファイルに全セッションが入るため、SessionEnd フック実行中に
    プロセスが落ちる(タイムアウト・スリープ・kill)と書き込み途中のファイルが
    残り、既存の取り込み結果を丸ごと失う。同じディレクトリの一時ファイルへ
    書いてから ``rename`` することで、読み手が中途半端な状態を見ることも
    なくなる(#42 のレビューで backfill.py 側にだけこの対策が入り、SessionEnd
    フックが実際に通るこの関数は素通しのままだった。#45 で気付いて統一した)。
    """
    directory = os.path.dirname(graph_path) or "."
    os.makedirs(directory, exist_ok=True)
    tmp = os.path.join(directory, f".{os.path.basename(graph_path)}.tmp{os.getpid()}")
    graph.save_to_file(tmp)
    os.chmod(tmp, 0o600)
    os.replace(tmp, graph_path)


def _edge_exists(graph: ContextGraph, source_id: str, target_id: str, edge_type: str) -> bool:
    for edge in graph._adjacency.get(source_id, []):
        if edge.target_id == target_id and edge.edge_type == edge_type:
            return True
    return False


def _turn_to_decision(turn: Turn) -> Decision:
    return Decision(
        decision_id=turn.decision_id,
        category=turn.category,
        scenario=turn.scenario,
        reasoning=turn.reasoning,
        outcome=turn.outcome,
        confidence=1.0,
        timestamp=turn.timestamp,
        decision_maker="claude-code",
        metadata={
            "session_id": turn.session_id,
            "message_uuid": turn.message_uuid,
            "parent_uuid": turn.parent_uuid,
            "tool_name": turn.tool_name,
            "rationale_source": turn.rationale_source,
            # 理由テキストまでに挟まっていた decision の数。照会側で弱い理由を
            # 絞り込めるようにしておく(距離を後から再計算するには transcript が
            # 必要になるため、書き込み時に残す)。
            "rationale_distance": turn.rationale_distance,
            # サブエージェント側の決定を識別する。親セッションの決定は None。
            "agent_id": turn.agent_id,
            "is_sidechain": turn.agent_id is not None,
        },
    )


def ingest_turns(
    graph: ContextGraph,
    turns: Iterable[Turn],
    source_documents: Optional[list] = None,
) -> dict:
    """Write turns into graph. Idempotent: re-ingesting the same turns is a no-op
    on node content (overwrite-in-place) and a true no-op on edges (skipped).

    Returns a small stats dict for observability.
    """
    recorder = DecisionRecorder(graph_store=graph)
    stats = {"decisions": 0, "entities_linked": 0, "causal_edges_added": 0, "causal_edges_skipped": 0}

    for turn in turns:
        decision = _turn_to_decision(turn)

        # record_decision() always stores the decision node (idempotent: dict
        # overwrite keyed by decision_id) but its own entities= param calls
        # link_entities() unconditionally, which is NOT idempotent (see
        # NOTES.md #5). So entities are linked manually below instead.
        recorder.record_decision(
            decision,
            entities=[],
            source_documents=source_documents or [turn.session_id],
        )
        stats["decisions"] += 1

        for entity in turn.entities:
            if entity.entity_id not in graph.nodes:
                graph.add_node(
                    entity.entity_id,
                    "Entity",
                    content=entity.content,
                    entity_type=entity.entity_type,
                )
            if not _edge_exists(graph, turn.decision_id, entity.entity_id, "ABOUT"):
                graph.add_edge(turn.decision_id, entity.entity_id, edge_type="ABOUT")
            stats["entities_linked"] += 1

        if turn.causal_parent_decision_id:
            if _edge_exists(graph, turn.causal_parent_decision_id, turn.decision_id, "CAUSED"):
                stats["causal_edges_skipped"] += 1
            else:
                graph.add_causal_relationship(
                    turn.causal_parent_decision_id, turn.decision_id, "CAUSED"
                )
                stats["causal_edges_added"] += 1

    return stats
