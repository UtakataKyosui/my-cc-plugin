"""Parse a Claude Code JSONL transcript into decision-graph-ready turns.

Idempotent by design: parsing the same transcript twice yields identical
``decision_id`` values (``<session_id>:<message_uuid>``), so re-running the
ingest is safe as long as the graph-side writer is also idempotent (see
``graph_ingest.py``).

Key finding (see ../NOTES.md #4): on this machine, ``thinking`` blocks are
always persisted with empty text (signature-only). ``_find_rationale`` falls
back to the nearest ancestor assistant turn's visible ``text`` content when
no non-empty thinking block is available.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

ENTITY_FILE_TOOLS = {"Edit", "Write", "Read", "NotebookEdit"}
ENTITY_AGENT_TOOLS = {"Agent", "Task"}
ENTITY_COMMAND_TOOLS = {"Bash"}

MAX_OUTCOME_CHARS = 800
MAX_SCENARIO_CHARS = 300
MAX_REASONING_CHARS = 1500
# 祖先探索はホップ数で打ち切らない。打ち切ると理由の被覆率がそのまま落ちる
# (上限 6 で 49.7%、無制限で 94.4%。NOTES.md #4)。代わりに「直近の本物の
# ユーザープロンプト」を境界として止める。境界を越えた text は別タスクの理由
# だからである。実測では境界越えは 4.6% しかないが、混ざると誤読を生む。
MAX_ANCESTOR_HOPS = 10_000

# ユーザーメッセージに混ざる、人間が書いたのではない注入物。フォールバックの
# 理由文として引用すると git status のダンプが理由になってしまうため取り除く。
_NOISE_PATTERNS = [
    re.compile(r"<system-reminder>.*?</system-reminder>", re.DOTALL),
    re.compile(r"<local-command-stdout>.*?</local-command-stdout>", re.DOTALL),
    re.compile(r"<local-command-caveat>.*?</local-command-caveat>", re.DOTALL),
    re.compile(r"<command-name>.*?</command-name>", re.DOTALL),
    re.compile(r"<command-message>.*?</command-message>", re.DOTALL),
    re.compile(r"<command-args>.*?</command-args>", re.DOTALL),
    re.compile(r"^Caveat:.*?(?=\n\n|\Z)", re.DOTALL | re.MULTILINE),
    re.compile(r"UserPromptSubmit hook additional context:.*\Z", re.DOTALL),
]


@dataclass
class Entity:
    entity_id: str
    entity_type: str
    content: str


@dataclass
class Turn:
    decision_id: str
    session_id: str
    message_uuid: str
    parent_uuid: Optional[str]
    timestamp: datetime
    tool_name: str
    tool_input: Dict[str, Any]
    category: str
    scenario: str
    reasoning: str
    rationale_source: str  # "thinking" | "text" | "user_prompt" | "none"
    outcome: str
    # 理由テキストまでに挟まっていた decision ターンの数。0 は直前のターンが
    # 理由を書いていたことを意味する。生のホップ数は tool_result を含んで
    # 倍になり読者に意味を持たないため、decision 数で数える。
    rationale_distance: int = 0
    # サブエージェント側のターンなら、その agentId。親セッションのターンでは None
    agent_id: Optional[str] = None
    # Agent/Task を起動したターンなら、起動した相手の agentId。
    # 親の decision とサブエージェントの decision を繋ぐ鍵になる
    spawned_agent_id: Optional[str] = None
    entities: List[Entity] = field(default_factory=list)
    causal_parent_decision_id: Optional[str] = None


def _normalize_path(path: str, cwd: Optional[str]) -> str:
    if not path:
        return path
    if not os.path.isabs(path) and cwd:
        path = os.path.join(cwd, path)
    return os.path.normpath(path)


def _entity_id_for_path(path: str) -> str:
    import hashlib

    h = hashlib.md5(path.encode("utf-8")).hexdigest()[:16]
    return f"file_{h}"


def _entity_id_for_command(command: str) -> str:
    import hashlib

    h = hashlib.md5(command.encode("utf-8")).hexdigest()[:16]
    return f"cmd_{h}"


def _entity_id_for_agent_type(agent_type: str) -> str:
    import hashlib

    h = hashlib.md5(agent_type.encode("utf-8")).hexdigest()[:16]
    return f"agent_{h}"


def _load_records(transcript_path: str) -> List[Dict[str, Any]]:
    records = []
    with open(transcript_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return records


def session_id_and_first_timestamp(transcript_path: str) -> "tuple[Optional[str], Optional[str]]":
    """transcript の session_id と最初に見つかる生の timestamp 文字列を返す。

    シャーディング(#43)のシャードキーはこの timestamp から作る。ファイルの
    mtime は再取り込みや `cp`/バックアップで変わり得るため使わない
    (同じセッションが再取り込みのたびに別の月のシャードへ書かれると、
    add_causal_relationship がシャードをまたぐ辺を静かに捨てる)。

    transcript の先頭数レコードには timestamp が無いことがある(実測: 最初の
    2-3 レコードが ``last-prompt``/``mode`` 等のメタレコードで timestamp
    フィールド自体を持たない)ため、最初に見つかった値を使う。
    """
    session_id = None
    timestamp = None
    for r in _load_records(transcript_path):
        if session_id is None:
            session_id = r.get("sessionId") or r.get("session_id")
        if timestamp is None:
            ts = r.get("timestamp")
            if isinstance(ts, str) and ts:
                timestamp = ts
        if session_id and timestamp:
            break
    if session_id is None:
        session_id = os.path.splitext(os.path.basename(transcript_path))[0]
    return session_id, timestamp


def _parse_timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            pass
    return datetime.utcnow()


def _content_blocks(record: Dict[str, Any]) -> List[Dict[str, Any]]:
    message = record.get("message")
    if not isinstance(message, dict):
        return []
    content = message.get("content")
    if isinstance(content, list):
        return [c for c in content if isinstance(c, dict)]
    if isinstance(content, str):
        return [{"type": "text", "text": content}]
    return []


def _tool_result_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for c in content:
            if isinstance(c, dict) and c.get("type") == "text":
                parts.append(c.get("text", ""))
        return "\n".join(parts)
    return ""


def _summarize(text: str, max_chars: int) -> str:
    text = (text or "").strip()
    if len(text) <= max_chars:
        return text
    return text[:max_chars].rstrip() + "…"


def _extract_entities(tool_name: str, tool_input: Dict[str, Any], cwd: Optional[str]) -> List[Entity]:
    entities: List[Entity] = []
    if tool_name in ENTITY_FILE_TOOLS:
        path = tool_input.get("file_path") or tool_input.get("path")
        if isinstance(path, str) and path:
            norm = _normalize_path(path, cwd)
            entities.append(Entity(_entity_id_for_path(norm), "file", norm))
    if tool_name in ENTITY_COMMAND_TOOLS:
        command = tool_input.get("command")
        if isinstance(command, str) and command.strip():
            entities.append(Entity(_entity_id_for_command(command.strip()), "command", command.strip()))
    if tool_name in ENTITY_AGENT_TOOLS:
        agent_type = tool_input.get("subagent_type") or tool_input.get("agent_type")
        if isinstance(agent_type, str) and agent_type:
            entities.append(Entity(_entity_id_for_agent_type(agent_type), "agent_type", agent_type))
    return entities


_AGENT_ID_RE = re.compile(r"agentId:\s*([0-9a-zA-Z_-]+)")
# バックグラウンドの slash コマンド起動(`/code-review low --fix ...` のような
# fork)は Agent/Task/Skill の tool_use を経由せず、`type: "system",
# subtype: "local_command"` レコードの `content` にこのマーカーで直接
# agentId を埋め込む。実測: #44 で見つかった13本の未リンクのうち1本がこの形。
_FORKED_SKILL_LAUNCH_RE = re.compile(r'<forked-skill-launch>(\{.*?\})</forked-skill-launch>')


def _spawned_agent_id(
    structured_agent_id: Optional[str], outcome_text: str
) -> Optional[str]:
    """起動した相手の agentId を取り出す。

    サブエージェントの transcript は ``<親セッションID>/subagents/agent-<agentId>.jsonl``
    に置かれ、``sessionId`` は親のものを持つ。親側でどの決定が誰を起動したかは
    tool_result にしか書かれていないため、ここで拾って因果の鍵にする。

    **``toolUseResult.agentId`` を主に使う。** これはレコード直下の構造化フィールドで、
    実測 349 件に存在する。本文テキストへの正規表現は当たらない形式があり、実測では
    これだけに頼ると 79 本が親へ繋がらなかった。テキストは形式が変わり得るので
    フォールバックに留める(切り詰める前の全文に当てること。outcome は 800 文字で
    切るため、切り詰め後に探すと取り落とす)。

    **ツール名でゲートしない。** エージェントの起動は ``Agent``/``Task`` 以外にも
    ``Skill`` 経由で起こる(実測 18 件)。``ENTITY_AGENT_TOOLS`` で先に弾くと、
    その分の親子関係が丸ごと落ちる。agentId が付いている tool_result はすべて
    起動として扱う。
    """
    if structured_agent_id:
        return structured_agent_id
    match = _AGENT_ID_RE.search(outcome_text or "")
    return match.group(1) if match else None


def _scenario_for_tool(tool_name: str, tool_input: Dict[str, Any]) -> str:
    if tool_name in ("Edit", "Write"):
        path = tool_input.get("file_path", "?")
        return _summarize(f"{tool_name} {path}", MAX_SCENARIO_CHARS)
    if tool_name == "Read":
        return _summarize(f"Read {tool_input.get('file_path', '?')}", MAX_SCENARIO_CHARS)
    if tool_name == "Bash":
        return _summarize(f"Bash: {tool_input.get('command', '?')}", MAX_SCENARIO_CHARS)
    if tool_name in ("Agent", "Task"):
        desc = tool_input.get("description") or tool_input.get("prompt", "")
        return _summarize(f"{tool_name}({tool_input.get('subagent_type', '?')}): {desc}", MAX_SCENARIO_CHARS)
    return _summarize(f"{tool_name}: {json.dumps(tool_input, ensure_ascii=False)}", MAX_SCENARIO_CHARS)


def _clean_user_text(text: str) -> str:
    """ユーザーメッセージから注入物を落として、人間が書いた本文だけを返す。"""
    for pattern in _NOISE_PATTERNS:
        text = pattern.sub("", text)
    return text.strip()


def _is_sidechain_root(record: Dict[str, Any]) -> bool:
    """サブエージェント transcript の先頭レコードか。

    そこに入っている text は、親がサブエージェントへ渡した委任指示そのものである。
    ``isMeta`` は立っているが、これは「システムが差し込んだ雑音」ではなく
    このエージェントが動いた理由そのものなので、除外してはいけない。実測では
    サブエージェント 363 本のうち 19 本がこの形で、除外すると そのファイルの
    全ターンの理由が空になる。
    """
    return bool(record.get("isSidechain")) and record.get("parentUuid") is None


def _user_prompt_text(record: Dict[str, Any]) -> Optional[str]:
    """本物のユーザープロンプトなら本文を返す。それ以外は None。

    ``isMeta`` が立っている user レコードは、人間がその場で書いたものではなく
    システムが差し込んだ文である(Skill 読み込みの通知、session-scoped Stop hook
    の通知、/loop の再開プロンプトなど)。実測ではここを通る user レコードの
    23.3% がこれに該当した。境界として数えると2つの壊れ方をする。

    1. 実際にはユーザーが書いていない文が rationale_source="user_prompt" として
       「なぜこのファイルを編集したか」の理由に入る
    2. 偽の境界で探索が止まり、その先にある本物の理由(text 祖先)へ届かなくなる

    どちらもこの機能の核心を壊すため、境界にも理由にもせず読み飛ばす。本物の
    ユーザープロンプトは、その先を辿れば必ず見つかる。


    slash コマンドの記録のように、注入物を落とすと本文が空になるものは
    境界としては数えたいが理由としては使えない。その場合は空文字を返し、
    呼び出し側が「境界だが理由にはならない」と扱えるようにする。
    """
    if record.get("type") != "user":
        return None
    if record.get("isMeta") and not _is_sidechain_root(record):
        return None
    if record.get("toolUseResult") is not None:
        return None
    blocks = _content_blocks(record)
    if any(b.get("type") == "tool_result" for b in blocks):
        return None
    raw = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    if not raw.strip():
        return None
    return _clean_user_text(raw)


class _AncestorIndex:
    """Look up assistant rationale text by walking the parentUuid chain."""

    def __init__(self, records: List[Dict[str, Any]]):
        self._by_uuid: Dict[str, Dict[str, Any]] = {}
        for r in records:
            u = r.get("uuid")
            if u:
                self._by_uuid[u] = r

    def find_rationale(
        self, start_parent_uuid: Optional[str], decision_uuids: set
    ) -> Tuple[str, str, int]:
        """Walk up parentUuid for this turn's rationale.

        Returns ``(reasoning, source, distance)`` where ``distance`` counts the
        decision turns passed on the way.

        Stops at the nearest genuine user prompt: text found beyond it belongs
        to a different task. If the boundary is reached first, the prompt itself
        becomes the rationale (the root premise), which keeps coverage at 100%
        with an honest label instead of an empty string.
        """
        current = start_parent_uuid
        hops = 0
        distance = 0
        while current and hops < MAX_ANCESTOR_HOPS:
            record = self._by_uuid.get(current)
            if record is None:
                break

            prompt = _user_prompt_text(record)
            if prompt is not None:
                # 境界に到達した。注入物を落として本文が残ればそれを理由にする。
                if prompt:
                    return _summarize(prompt, MAX_REASONING_CHARS), "user_prompt", distance
                return "", "none", distance

            if record.get("type") == "assistant":
                blocks = _content_blocks(record)
                thinking = "".join(
                    b.get("thinking", "") for b in blocks if b.get("type") == "thinking"
                ).strip()
                if thinking:
                    return _summarize(thinking, MAX_REASONING_CHARS), "thinking", distance
                text = "".join(
                    b.get("text", "") for b in blocks if b.get("type") == "text"
                ).strip()
                has_tool_use = any(b.get("type") == "tool_use" for b in blocks)
                if text and not has_tool_use:
                    return _summarize(text, MAX_REASONING_CHARS), "text", distance
                if has_tool_use and current in decision_uuids:
                    distance += 1

            current = record.get("parentUuid")
            hops += 1
        return "", "none", distance


def collect_spawned_agent_ids(transcript_path: str) -> Dict[str, str]:
    """この transcript の中で起動された agentId をすべて集める。

    ``parse_transcript``/``parse_subagent_transcript`` は tool_use を含む
    assistant ターンだけを decision 化するため、agentId の収集にはこの専用の
    走査を使う。理由は2つある。

    1. サブエージェントが**さらに別のサブエージェントを起動する**(nested)場合、
       起動の記録は「サブエージェント自身の transcript」の中にあり、親の
       トップレベル transcript には一切現れない。#44 で見つかった13本の
       未リンクのうち6本がこの形だった。トップレベル transcript だけを見ていると
       この層が丸ごと抜ける
    2. バックグラウンドの slash コマンド起動(``/code-review low --fix 3,4,9``)は
       ``Agent``/``Task``/``Skill`` の tool_use を経由せず、``type: "system",
       subtype: "local_command"`` レコードの ``content`` に
       ``<forked-skill-launch>{"agentId": ...}</forked-skill-launch>`` という
       マーカーで直接 agentId を埋め込む。tool_use を起点に探す既存のロジックでは
       この経路を見つけられない

    戻り値は ``{agentId: 起動した側の decision_id}``。呼び出し側はこれを複数の
    transcript から集めてマージし、多段の親子関係を辿れるようにする。
    """
    records = _load_records(transcript_path)
    if not records:
        return {}

    session_id = None
    for r in records:
        session_id = r.get("sessionId") or r.get("session_id")
        if session_id:
            break
    if session_id is None:
        session_id = os.path.splitext(os.path.basename(transcript_path))[0]

    result: Dict[str, str] = {}

    # 経路1: tool_use を含む assistant ターンの tool_result から。
    # tool_results/agentId は transcript 全体を1回走査して辞書にする
    # (tool_use ごとに毎回走査すると O(n^2) になる)。
    tool_result_texts: Dict[str, str] = {}
    tool_result_agent_ids: Dict[str, str] = {}
    for r in records:
        if r.get("type") != "user":
            continue
        structured = r.get("toolUseResult")
        agent_id_field = (
            structured.get("agentId") if isinstance(structured, dict) else None
        )
        for block in _content_blocks(r):
            if block.get("type") == "tool_result":
                tool_use_id = block.get("tool_use_id")
                if tool_use_id:
                    tool_result_texts[tool_use_id] = _tool_result_text(block.get("content"))
                    if agent_id_field:
                        tool_result_agent_ids[tool_use_id] = agent_id_field

    for r in records:
        if r.get("type") != "assistant":
            continue
        message_uuid = r.get("uuid")
        if not message_uuid:
            continue
        for block in _content_blocks(r):
            if block.get("type") != "tool_use":
                continue
            tool_use_id = block.get("id", "")
            spawned = _spawned_agent_id(
                tool_result_agent_ids.get(tool_use_id),
                tool_result_texts.get(tool_use_id, ""),
            )
            if spawned:
                result[spawned] = f"{session_id}:{message_uuid}"

    # 経路2: system/local_command レコードの forked-skill-launch マーカーから
    for r in records:
        if r.get("type") != "system":
            continue
        content = r.get("content")
        if not isinstance(content, str):
            continue
        match = _FORKED_SKILL_LAUNCH_RE.search(content)
        if not match:
            continue
        try:
            payload = json.loads(match.group(1))
        except (ValueError, TypeError):
            continue
        agent_id = payload.get("agentId")
        message_uuid = r.get("uuid")
        if agent_id and message_uuid:
            result[agent_id] = f"{session_id}:{message_uuid}"

    return result


def parse_subagent_transcript(
    transcript_path: str, causal_parent_by_agent: Optional[Dict[str, str]] = None
) -> List[Turn]:
    """サブエージェントの transcript を decision の列にする。

    ``<親セッションID>/subagents/agent-<agentId>.jsonl`` に置かれたファイルを読む。
    レコードは全て ``isSidechain: true`` なので ``parse_transcript`` はこれを
    1件も返さない。実測では 1056 本のうち 359 本がこの形で、1本あたり 20〜40 件の
    tool_use を含んでいた。取り込まないとサブエージェントに委譲した作業の
    「なぜ」が丸ごと欠ける。

    ``session_id`` はファイル内の ``sessionId``(親セッションのID)を使う。
    ``decision_id`` は ``<session_id>:<message_uuid>`` のままで、uuid が一意なので
    親のターンと衝突しない。

    ``causal_parent_by_agent`` に ``{agentId: 親の decision_id}`` を渡すと、
    サブエージェントの最初の決定を親の Agent 呼び出しへ ``CAUSED`` で繋ぐ。
    """
    turns = parse_transcript(transcript_path, include_sidechain=True)
    if not turns:
        return []

    agent_id = None
    for record in _load_records(transcript_path):
        if record.get("agentId"):
            agent_id = record["agentId"]
            break

    parent_decision = (causal_parent_by_agent or {}).get(agent_id or "")
    for turn in turns:
        turn.agent_id = agent_id
    # 先頭の決定だけを親へ繋ぐ。2件目以降はファイル内の parentUuid で既に繋がっている。
    if parent_decision and turns[0].causal_parent_decision_id is None:
        turns[0].causal_parent_decision_id = parent_decision
    return turns


def parse_transcript(
    transcript_path: str,
    session_id: Optional[str] = None,
    include_sidechain: bool = False,
) -> List[Turn]:
    """Parse one JSONL transcript into a list of decision Turns (main chain only).

    Sidechain records (``isSidechain: true``, i.e. subagent-internal transcripts)
    are skipped for this MVP — the subagent invocation itself is still captured
    as a Turn on the main chain (the ``Agent``/``Task`` tool_use).
    """
    records = _load_records(transcript_path)
    if not records:
        return []

    if session_id is None:
        for r in records:
            session_id = r.get("sessionId") or r.get("session_id")
            if session_id:
                break
    if session_id is None:
        session_id = os.path.splitext(os.path.basename(transcript_path))[0]

    # tool_use_id -> tool_result content text, from user records.
    def _excluded(record: Dict[str, Any]) -> bool:
        return bool(record.get("isSidechain")) and not include_sidechain

    tool_results: Dict[str, str] = {}
    # tool_use_id -> toolUseResult.agentId。レコード直下の構造化フィールドで、
    # 本文テキストには現れない形式があるためこちらを主に使う(_spawned_agent_id)。
    tool_result_agent_ids: Dict[str, str] = {}
    for r in records:
        if r.get("type") != "user" or _excluded(r):
            continue
        structured = r.get("toolUseResult")
        agent_id_field = (
            structured.get("agentId") if isinstance(structured, dict) else None
        )
        for block in _content_blocks(r):
            if block.get("type") == "tool_result":
                tool_use_id = block.get("tool_use_id")
                if tool_use_id:
                    tool_results[tool_use_id] = _tool_result_text(block.get("content"))
                    if agent_id_field:
                        tool_result_agent_ids[tool_use_id] = agent_id_field

    ancestor_index = _AncestorIndex(records)

    # 理由テキストまでの距離を decision 数で数えるために、どの uuid が decision
    # ターンかを先に確定しておく。
    decision_uuids = {
        r.get("uuid")
        for r in records
        if r.get("type") == "assistant"
        and not _excluded(r)
        and any(b.get("type") == "tool_use" for b in _content_blocks(r))
        and r.get("uuid")
    }

    # Track the most recent decision_id emitted for this session, to link
    # causal edges without re-walking the whole chain.
    decision_id_by_uuid: Dict[str, str] = {}
    turns: List[Turn] = []

    for r in records:
        if r.get("type") != "assistant" or _excluded(r):
            continue
        blocks = _content_blocks(r)
        tool_use = next((b for b in blocks if b.get("type") == "tool_use"), None)
        if tool_use is None:
            continue

        message_uuid = r.get("uuid")
        parent_uuid = r.get("parentUuid")
        if not message_uuid:
            continue

        tool_name = tool_use.get("name", "unknown")
        tool_input = tool_use.get("input") or {}
        cwd = r.get("cwd")

        reasoning, rationale_source, rationale_distance = ancestor_index.find_rationale(
            parent_uuid, decision_uuids
        )

        outcome_text = tool_results.get(tool_use.get("id", ""), "")
        outcome = _summarize(outcome_text, MAX_OUTCOME_CHARS) if outcome_text else "(no tool_result captured)"
        spawned = _spawned_agent_id(
            tool_result_agent_ids.get(tool_use.get("id", "")), outcome_text
        )

        decision_id = f"{session_id}:{message_uuid}"

        # Walk up parentUuid to find the nearest ancestor that is itself a
        # decision turn (i.e. already emitted), for the causal edge.
        causal_parent = None
        cursor = parent_uuid
        hops = 0
        while cursor and hops < MAX_ANCESTOR_HOPS:
            if cursor in decision_id_by_uuid:
                causal_parent = decision_id_by_uuid[cursor]
                break
            parent_record = ancestor_index._by_uuid.get(cursor)
            if parent_record is None:
                break
            cursor = parent_record.get("parentUuid")
            hops += 1

        turn = Turn(
            decision_id=decision_id,
            session_id=session_id,
            message_uuid=message_uuid,
            parent_uuid=parent_uuid,
            timestamp=_parse_timestamp(r.get("timestamp")),
            tool_name=tool_name,
            tool_input=tool_input,
            category=f"tool_use:{tool_name}",
            scenario=_scenario_for_tool(tool_name, tool_input),
            reasoning=reasoning,
            rationale_source=rationale_source,
            rationale_distance=rationale_distance,
            spawned_agent_id=spawned,
            outcome=outcome,
            entities=_extract_entities(tool_name, tool_input, cwd),
            causal_parent_decision_id=causal_parent,
        )
        turns.append(turn)
        decision_id_by_uuid[message_uuid] = decision_id

    return turns
