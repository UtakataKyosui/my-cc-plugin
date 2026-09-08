"""ゲート: 実 transcript から「なぜこのファイルを触ったか」をグラフから再現できる。

再現できなければスキーマが誤っている(NOTES.md の設計方針)。実データが要る。
指定が無ければ skip する(conftest.py の real_transcript を参照)。

``semantica.context`` の import はテスト関数の中で行う。理由は test_idempotency.py
と同じ(モジュール直下の import は skip されても収集時に他のテストを汚染する)。
"""

from lib.transcript_parser import parse_transcript


def test_reproduces_why_a_file_was_touched(real_transcript):
    from semantica.context import ContextGraph

    from lib.graph_ingest import ingest_turns
    from lib.query import decisions_about_file

    turns = parse_transcript(real_transcript)
    assert turns, f"no tool-use turns found in {real_transcript}"

    file_turns = [t for t in turns if any(e.entity_type == "file" for e in t.entities)]
    assert file_turns, f"no file-touching turns in {real_transcript}; pick a different one"

    target = file_turns[0]
    file_entity = next(e for e in target.entities if e.entity_type == "file")

    graph = ContextGraph(advanced_analytics=False)
    ingest_turns(graph, turns)

    rows = decisions_about_file(graph, file_entity.content)
    matching = [r for r in rows if r["decision_id"] == target.decision_id]

    assert matching, (
        f"could not find decision {target.decision_id} via decisions_about_file"
        f"({file_entity.content!r})"
    )
    assert matching[0]["reasoning"].strip(), (
        f"decision {target.decision_id} was found but its reasoning is empty"
    )
