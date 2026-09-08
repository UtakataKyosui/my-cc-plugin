"""同一セッションを2回 ingest してもノード・エッジが重複しないことを固定する。

実データが要る。指定が無ければ skip する(conftest.py の real_transcript を参照)。

``semantica.context`` の import はテスト関数の中で行う。モジュール直下で import
すると、この検査が skip されてもテスト**収集**の時点で semantica が読み込まれ、
同じ pytest プロセス内の他のテスト(test_mcp_server.py の「semantica を起動時に
import していないか」の検査)を汚染する。
"""

from lib.transcript_parser import parse_transcript


def test_reingest_is_idempotent(real_transcript):
    from semantica.context import ContextGraph

    from lib.graph_ingest import ingest_turns

    turns = parse_transcript(real_transcript)
    assert turns, f"no tool-use turns found in {real_transcript}"

    graph = ContextGraph(advanced_analytics=False)

    stats1 = ingest_turns(graph, turns)
    after_first = graph.stats()

    stats2 = ingest_turns(graph, turns)
    after_second = graph.stats()

    assert after_first["node_count"] == after_second["node_count"], (
        f"node_count changed on re-ingest: "
        f"{after_first['node_count']} -> {after_second['node_count']}"
    )
    assert after_first["edge_count"] == after_second["edge_count"], (
        f"edge_count changed on re-ingest: "
        f"{after_first['edge_count']} -> {after_second['edge_count']}"
    )
    assert stats2["causal_edges_added"] == 0, (
        f"second ingest should add 0 new causal edges, added {stats2['causal_edges_added']}"
    )
