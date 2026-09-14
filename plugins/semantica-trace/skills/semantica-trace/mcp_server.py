"""照会専用の stdio MCP サーバー。

記録はしない。SessionEnd フック(``ingest_session.sh``)だけが書き込み、この
サーバーは読むだけである。モデルに記録させると、記録するかどうかがモデルの
判断次第になって欠落が起き、エージェントループも汚れる(Issue #39 の設計方針)。

**semantica を起動時に import しない。** import に実測 5.6 秒かかり、stdio の
MCP サーバーはセッション開始ごとに起動されるため、全セッションがその 5.6 秒を
払うことになる。グラフの読み込みも最初のツール呼び出しまで遅延させる。

起動:
    ~/.cache/semantica-trace/.venv/bin/python ~/.claude/skills/semantica-trace/mcp_server.py
"""

from __future__ import annotations

import os
import sys
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from mcp.server.mcpserver import MCPServer  # noqa: E402

server = MCPServer(
    name="semantica-trace",
    instructions=(
        "Claude Code の過去セッションの決定グラフを照会する。読み取り専用。"
        "記録は SessionEnd フックが行うため、このサーバーに書き込む手段はない。"
    ),
)

# シャードごとにロード済みグラフを保持する({path: (mtime, graph)})。
# シャード分割(#43)後は、SessionEnd が触るのは常に「今月」のシャード1本だけ
# なので、他の月のキャッシュは触れる限り再利用され続ける。単一の全期間グラフ
# だった頃は、どのセッションが終わってもキャッシュ全体を読み直す必要があった。
_shard_cache: Dict[str, "tuple[float, Any]"] = {}


def _graph_path() -> str:
    """後方互換用。単一ファイルモード(SEMANTICA_TRACE_GRAPH 明示時)のパスを返す。"""
    from lib.graph_ingest import DEFAULT_GRAPH_PATH

    return os.environ.get("SEMANTICA_TRACE_GRAPH", DEFAULT_GRAPH_PATH)


def _graph_dir() -> str:
    from lib.graph_ingest import DEFAULT_GRAPH_DIR

    return os.environ.get("SEMANTICA_TRACE_GRAPH_DIR", DEFAULT_GRAPH_DIR)


def _load_shards() -> List[Any]:
    """全シャードを読む。ファイルが更新されているシャードだけ読み直す。

    ``SEMANTICA_TRACE_GRAPH`` が明示されている場合(テスト・単一ファイル互換)
    はそのファイル1本だけを単一シャードとして扱う。
    """
    from semantica.context import ContextGraph

    if "SEMANTICA_TRACE_GRAPH" in os.environ:
        paths = [_graph_path()] if os.path.exists(_graph_path()) else []
    else:
        from lib.graph_ingest import has_legacy_single_graph, list_shard_paths

        paths = list_shard_paths(_graph_dir())
        if not paths:
            # シャーディング導入(#43)より前に作られた単一ファイルがまだ
            # 残っている場合、backfill --fresh で移行するまでの間、それを
            # 唯一のシャードとして読む。これが無いと、マージ直後に全クエリが
            # 「グラフが無い」を返し、既存の全履歴が消えたように見える
            # (実測で再現した)。
            legacy = has_legacy_single_graph(_graph_dir())
            if legacy:
                paths = [legacy]

    graphs = []
    seen_paths = set(paths)
    for path in paths:
        mtime = os.path.getmtime(path)
        cached = _shard_cache.get(path)
        if cached is None or cached[0] != mtime:
            g = ContextGraph(advanced_analytics=False)
            g.load_from_file(path)
            _shard_cache[path] = (mtime, g)
        graphs.append(_shard_cache[path][1])

    # 消えた(リネーム・削除された)シャードのキャッシュは捨てる
    for stale in list(_shard_cache):
        if stale not in seen_paths:
            del _shard_cache[stale]

    return graphs


def _resolve(file_path: str) -> str:
    """相対パスを絶対パスへ寄せる。

    エンティティ ID は絶対パス文字列の md5 なので、相対パスをそのまま渡すと
    ID が一致せず必ず 0 件になる。0 件は「触っていない」と読めてしまい、
    黙って間違った結論を出すため、入口で正規化する。
    """
    return os.path.normpath(os.path.abspath(os.path.expanduser(file_path)))


def _no_graph() -> Dict[str, Any]:
    return {
        "error": "グラフがまだ無い",
        "graph_dir": _graph_dir(),
        "hint": (
            "SessionEnd フックがまだ一度も走っていない可能性がある。"
            "旧来の単一ファイル(graph.json)からシャード構成へ移行していない"
            "可能性もある。過去セッションを入れるには lib.backfill --fresh を直接呼ぶ。"
        ),
    }


@server.tool(
    description=(
        "指定したファイルについて、過去の全セッションを横断して「なぜ触ったか」を"
        "時系列で返す。reasoning が理由、rationale_source はその出どころ"
        "(text はアシスタントの発言、user_prompt は利用者の指示)。"
        "rationale_distance が大きいほど理由が遠い。"
    )
)
def decisions_about_file(file_path: str, limit: int = 50) -> Dict[str, Any]:
    graphs = _load_shards()
    if not graphs:
        return _no_graph()
    from lib.query import decisions_about_file_multi as _impl

    resolved = _resolve(file_path)
    rows = _impl(graphs, resolved)
    return {
        "file_path": resolved,
        "total": len(rows),
        "returned": min(len(rows), limit),
        "decisions": rows[:limit],
    }


@server.tool(
    description=(
        "指定したファイルを触ったセッション ID の一覧を返す。"
        "どのセッションを読み返すべきか当たりをつけるのに使う。"
    )
)
def sessions_touching_file(file_path: str) -> Dict[str, Any]:
    graphs = _load_shards()
    if not graphs:
        return _no_graph()
    from lib.query import sessions_touching_file_multi as _impl

    resolved = _resolve(file_path)
    sessions = _impl(graphs, resolved)
    return {"file_path": resolved, "session_count": len(sessions), "session_ids": sessions}


@server.tool(
    description=(
        "ある決定の因果チェーンを辿る。direction は upstream(何がこの決定を"
        "引き起こしたか)または downstream(この決定が何を引き起こしたか)。"
        "decision_id は decisions_about_file が返す値を使う。"
    )
)
def causal_chain(decision_id: str, direction: str = "upstream") -> Dict[str, Any]:
    if direction not in ("upstream", "downstream"):
        return {"error": "direction は upstream か downstream", "given": direction}
    graphs = _load_shards()
    if not graphs:
        return _no_graph()
    from lib.query import causal_chain_multi as _impl

    chain = _impl(graphs, decision_id, direction=direction)
    return {"decision_id": decision_id, "direction": direction, "length": len(chain), "chain": chain}


@server.tool(
    description=(
        "グラフ全体の規模と、取り込み済みのセッション数を返す。"
        "照会結果が空だったときに、グラフが空なのか条件が外れたのかを切り分ける。"
    )
)
def graph_stats() -> Dict[str, Any]:
    graphs = _load_shards()
    if not graphs:
        return _no_graph()
    from lib.query import graph_stats_multi as _impl

    merged = _impl(graphs)
    return {
        "graph_dir": _graph_dir(),
        "shard_count": len(graphs),
        "statistics": {
            "node_count": merged["node_count"],
            "edge_count": merged["edge_count"],
            "node_types": merged["node_types"],
        },
        "session_count": merged["session_count"],
    }


if __name__ == "__main__":
    server.run(transport="stdio")
