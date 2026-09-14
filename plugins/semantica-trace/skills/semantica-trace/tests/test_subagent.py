"""サブエージェントの取り込みが保証すべき性質を固定する。

PR #42 のレビューで、この経路にテストが1件も無く、実際に2種類のバグ
(agentId を構造化フィールドから取らない / サブエージェントの根の委任指示を
捨てる)がテストなしで通っていたことが判明した。同じ穴を開けないため、
壊れると黙って誤答する経路だけを検査する。
"""

import json
import os

from lib.transcript_parser import (
    _is_sidechain_root,
    _spawned_agent_id,
    _user_prompt_text,
    collect_spawned_agent_ids,
    parse_subagent_transcript,
    parse_transcript,
)


def test_structured_agent_id_is_used_first():
    """agentId は構造化フィールドを主に使う。

    テキストへの正規表現だけに頼ると実測 79 本が親へ繋がらなかった。
    """
    assert _spawned_agent_id("abc123", "") == "abc123"


def test_text_fallback_still_works_without_structured_field():
    assert _spawned_agent_id(None, "... agentId: def456 ...") == "def456"


def test_no_agent_id_is_invented_from_unrelated_text():
    assert _spawned_agent_id(None, "no agent here") is None


def test_structured_field_wins_over_conflicting_text():
    assert _spawned_agent_id("structured", "agentId: fromtext") == "structured"


def test_sidechain_root_delegation_instruction_is_kept():
    """サブエージェント transcript の根の isMeta レコードは理由に使う。

    そこに入っているのは親からの委任指示そのもので、捨てるとそのファイルの
    全ターンの理由が空になる。
    """
    root = {
        "type": "user",
        "isMeta": True,
        "isSidechain": True,
        "parentUuid": None,
        "message": {"content": [{"type": "text", "text": "Review target: 3,4,9"}]},
    }
    assert _is_sidechain_root(root)
    assert _user_prompt_text(root) == "Review target: 3,4,9"


def test_mid_conversation_ismeta_noise_is_discarded():
    """会話中に差し込まれた isMeta は雑音なので捨てる。

    サブエージェントの根の委任指示(上のテスト)とこれを取り違えないことを固定する。
    """
    mid = {
        "type": "user",
        "isMeta": True,
        "isSidechain": True,
        "parentUuid": "some-uuid",
        "message": {"content": [{"type": "text", "text": "A Stop hook is now active"}]},
    }
    assert _user_prompt_text(mid) is None


def test_parent_session_ismeta_is_discarded():
    """親セッション側の isMeta は捨てる(parentUuid が None でも sidechain でないため)。"""
    parent_meta = {
        "type": "user",
        "isMeta": True,
        "parentUuid": None,
        "message": {"content": [{"type": "text", "text": "injected"}]},
    }
    assert _user_prompt_text(parent_meta) is None


def test_forked_skill_launch_marker_is_extracted(tmp_path):
    """バックグラウンドの slash コマンド起動を forked-skill-launch マーカーから拾う。

    ``/code-review low --fix 3,4,9`` のような起動は Agent/Task/Skill の
    tool_use を経由せず、``type: "system", subtype: "local_command"``
    レコードの ``content`` にこのマーカーで直接 agentId を埋め込む(#44 実測)。
    """
    record = {
        "type": "system",
        "subtype": "local_command",
        "uuid": "sys-uuid-1",
        "sessionId": "sess-x",
        "content": (
            "<local-command-stdout>Running in the background as "
            "@code-review</local-command-stdout>\n"
            '<forked-skill-launch>{"agentId":"testagent123","skillName":'
            '"code-review","description":"/code-review low"}</forked-skill-launch>'
        ),
    }
    path = tmp_path / "parent.jsonl"
    path.write_text(json.dumps(record) + "\n")

    result = collect_spawned_agent_ids(str(path))
    assert result.get("testagent123") == "sess-x:sys-uuid-1"


def test_nested_subagent_spawn_is_collected(tmp_path):
    """サブエージェントが別のサブエージェントを起動した場合も拾う。

    起動の記録はサブエージェント自身の transcript の中にあり、トップレベルの
    親 transcript には現れない。トップレベルだけを走査すると、この層が
    丸ごと落ちる(#44 実測: 未リンク13本のうち6本がこれだった)。
    """
    grandchild_launch = {
        "type": "user",
        "uuid": "u-1",
        "sessionId": "sess-y",
        "isSidechain": True,
        "message": {
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": "tu-1",
                    "content": "Async agent launched successfully.",
                }
            ]
        },
        "toolUseResult": {"status": "async_launched", "agentId": "grandchild456"},
    }
    launcher = {
        "type": "assistant",
        "uuid": "a-1",
        "sessionId": "sess-y",
        "isSidechain": True,
        "message": {
            "content": [{"type": "tool_use", "id": "tu-1", "name": "Agent", "input": {}}]
        },
    }
    path = tmp_path / "subagent.jsonl"
    path.write_text(json.dumps(launcher) + "\n" + json.dumps(grandchild_launch) + "\n")

    result = collect_spawned_agent_ids(str(path))
    # decision_id は {session}:{message_uuid}:{tool_use_id} 形式(1メッセージに
    # 複数 tool_use がある場合の一意化のため tool_use_id を含む)。
    assert result.get("grandchild456") == "sess-y:a-1:tu-1"


def test_real_subagent_transcript_has_a_consistent_agent_id(real_subagent_transcript):
    turns = parse_subagent_transcript(real_subagent_transcript, {"nonexistent": "x"})
    assert turns, f"no turns parsed from {real_subagent_transcript}"
    assert turns[0].agent_id, "agent_id was not extracted"
    assert all(t.agent_id == turns[0].agent_id for t in turns), (
        "agent_id varies across turns of the same subagent transcript"
    )
    # 存在しない agentId を渡したので、この causal_parent_by_agent からは繋がらないはず
    assert turns[0].causal_parent_decision_id is None, (
        "causal parent was linked from an unrelated agentId"
    )


def test_parent_parse_still_excludes_sidechain_by_default(real_transcript):
    """`include_sidechain` の追加が既存経路の挙動を変えていないことを確認する。"""
    default = parse_transcript(real_transcript)
    explicit = parse_transcript(real_transcript, include_sidechain=False)
    assert len(default) == len(explicit)
