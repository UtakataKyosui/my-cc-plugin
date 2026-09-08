"""rationale の解決が保証すべき性質を固定する。

被覆率の数値そのものは transcript に依存して動くため assert しない。代わりに
「壊れたら理由が読めなくなる」性質だけを検査する。
"""

from lib.transcript_parser import (
    MAX_ANCESTOR_HOPS,
    _clean_user_text,
    _user_prompt_text,
    parse_transcript,
)

NOISE_MARKERS = [
    "<system-reminder>",
    "<local-command-stdout>",
    "<command-name>",
    "UserPromptSubmit hook additional context:",
]


def test_hop_cap_has_not_come_back():
    """祖先探索がホップ数で打ち切られていない。

    打ち切ると被覆率がそのまま落ちる(実測: 上限6で49.7%、無制限で94.4%)。
    """
    assert MAX_ANCESTOR_HOPS >= 1000, (
        f"MAX_ANCESTOR_HOPS={MAX_ANCESTOR_HOPS} is a hop cap again; "
        "coverage tracks this number directly (6 -> 49.7%)"
    )


def test_noise_only_user_text_is_discarded():
    """注入物だけの記録は理由に使わない。"""
    assert _clean_user_text("<system-reminder>x</system-reminder>") == ""


def test_ismeta_boundary_is_not_treated_as_a_prompt():
    """isMeta の user レコードは境界にも理由にもしない。

    境界扱いすると (a) システムが差し込んだ文が「利用者の指示」として理由に入り、
    (b) 偽の境界で探索が止まって本物の理由へ届かなくなる。
    """
    meta_record = {
        "type": "user",
        "isMeta": True,
        "message": {
            "content": [{"type": "text", "text": "A session-scoped Stop hook is now active"}]
        },
    }
    assert _user_prompt_text(meta_record) is None


def test_genuine_user_prompt_is_recognised():
    genuine = {
        "type": "user",
        "message": {"content": [{"type": "text", "text": "これを直して"}]},
    }
    assert _user_prompt_text(genuine) == "これを直して"


def test_rationale_resolution_on_real_transcript(real_transcript):
    """実データに対して4つの保証をまとめて検査する。

    1. 注入物が reasoning に混ざらない
    2. rationale_source が none のまま残らない(境界が100%到達可能なため)
    3. rationale_distance は非負
    4. source が none 以外なら reasoning は空でない
    """
    turns = parse_transcript(real_transcript)
    assert turns, f"no tool-use turns found in {real_transcript}"

    leaked = [
        (t.decision_id, marker)
        for t in turns
        for marker in NOISE_MARKERS
        if marker in t.reasoning
    ]
    assert not leaked, f"noise leaked into reasoning: {leaked[:5]}"

    unresolved = [t.decision_id for t in turns if t.rationale_source == "none"]
    assert not unresolved, (
        f"{len(unresolved)}/{len(turns)} turns have rationale_source=none "
        "(the user-prompt boundary should always be reachable)"
    )

    negative_distance = [t.decision_id for t in turns if t.rationale_distance < 0]
    assert not negative_distance, f"negative rationale_distance: {negative_distance[:5]}"

    empty_reasoning = [
        t.decision_id for t in turns if t.rationale_source != "none" and not t.reasoning.strip()
    ]
    assert not empty_reasoning, (
        f"source is not none but reasoning is empty: {empty_reasoning[:5]}"
    )
