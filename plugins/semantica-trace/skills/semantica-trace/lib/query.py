"""Cross-session query helpers over the semantica decision graph.

Requires the isolated venv at ~/.cache/semantica-trace/.venv.
"""

from __future__ import annotations

import os
from typing import Any, Dict, List

from semantica.context import ContextGraph

from .graph_ingest import DEFAULT_GRAPH_PATH
from .transcript_parser import _entity_id_for_path


def decisions_about_file(graph: ContextGraph, file_path: str) -> List[Dict[str, Any]]:
    """All decisions (across all ingested sessions) linked to a given file path.

    Returns dicts with session_id, scenario, reasoning, outcome, timestamp —
    ordered by timestamp so the story of "why was this file touched" reads
    chronologically.
    """
    norm = os.path.normpath(file_path)
    entity_id = _entity_id_for_path(norm)

    results = []
    for edge in graph.find_edges(edge_type="ABOUT"):
        if edge["target"] != entity_id:
            continue
        node = graph.find_node(edge["source"])
        if not node:
            continue
        meta = node["metadata"]
        results.append(
            {
                "decision_id": node["id"],
                "session_id": meta.get("session_id"),
                "tool_name": meta.get("tool_name"),
                "scenario": meta.get("scenario", node["content"]),
                "reasoning": meta.get("reasoning", ""),
                "rationale_source": meta.get("rationale_source"),
                "outcome": meta.get("outcome", ""),
                "timestamp": meta.get("timestamp"),
            }
        )
    results.sort(key=lambda r: r.get("timestamp") or "")
    return results


def causal_chain(graph: ContextGraph, decision_id: str, direction: str = "upstream") -> List[Dict[str, Any]]:
    chain = graph.get_causal_chain(decision_id, direction=direction)
    return [
        {
            "decision_id": d.decision_id,
            "scenario": d.scenario,
            "reasoning": d.reasoning,
            "outcome": d.outcome,
            "causal_distance": d.metadata.get("causal_distance"),
        }
        for d in chain
    ]


def sessions_touching_file(graph: ContextGraph, file_path: str) -> List[str]:
    seen = []
    for row in decisions_about_file(graph, file_path):
        sid = row["session_id"]
        if sid and sid not in seen:
            seen.append(sid)
    return seen


def load_default_graph() -> ContextGraph:
    graph = ContextGraph(advanced_analytics=False)
    if os.path.exists(DEFAULT_GRAPH_PATH):
        graph.load_from_file(DEFAULT_GRAPH_PATH)
    return graph


# --- 複数シャード横断のクエリ(#43) -----------------------------------------
#
# decisions_about_file / sessions_touching_file はファイルがどの月に触られたか
# 分からないため、全シャードを見て回る必要がある。causal_chain は逆に、
# CAUSED の辺がほぼ100%セッション内(= 同じシャード内)に閉じている実測
# (44154本中2本だけがセッションをまたぐ)を利用して、decision_id を持つ
# シャード1本だけを見れば済む。


def decisions_about_file_multi(graphs: List[ContextGraph], file_path: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for graph in graphs:
        rows.extend(decisions_about_file(graph, file_path))
    rows.sort(key=lambda r: r.get("timestamp") or "")
    return rows


def sessions_touching_file_multi(graphs: List[ContextGraph], file_path: str) -> List[str]:
    seen: List[str] = []
    for row in decisions_about_file_multi(graphs, file_path):
        sid = row["session_id"]
        if sid and sid not in seen:
            seen.append(sid)
    return seen


def causal_chain_multi(
    graphs: List[ContextGraph], decision_id: str, direction: str = "upstream"
) -> List[Dict[str, Any]]:
    for graph in graphs:
        if graph.find_node(decision_id):
            return causal_chain(graph, decision_id, direction=direction)
    return []


def graph_stats_multi(graphs: List[ContextGraph]) -> Dict[str, Any]:
    node_count = 0
    edge_count = 0
    node_types: Dict[str, int] = {}
    sessions = set()
    for graph in graphs:
        stats = graph.stats()
        node_count += stats.get("node_count", 0)
        edge_count += stats.get("edge_count", 0)
        for k, v in (stats.get("node_types") or {}).items():
            node_types[k] = node_types.get(k, 0) + v
        for node in graph.find_nodes(node_type="Decision"):
            sid = (node.get("metadata") or {}).get("session_id")
            if sid:
                sessions.add(sid)
    return {
        "node_count": node_count,
        "edge_count": edge_count,
        "node_types": node_types,
        "session_count": len(sessions),
    }
