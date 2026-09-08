"""semantica-trace のテスト共通設定。

実行:
    cd ~/.claude/skills/semantica-trace
    ~/.cache/semantica-trace/.venv/bin/python -m pytest tests/

実 transcript を要するテストは既定で skip する。transcript には実際の会話内容が
入っており、CI にチェックインできる形にすると SKILL.md の「機微情報」の方針に反する。
ローカルで実データを使って検査する場合だけ `--transcript` / `--subagent-transcript`
を渡す。

    ~/.cache/semantica-trace/.venv/bin/python -m pytest tests/ \\
        --transcript ~/.claude/projects/-Users-<user>--claude/<session-id>.jsonl \\
        --subagent-transcript ~/.claude/projects/.../subagents/agent-<id>.jsonl
"""

from __future__ import annotations

import os
import sys

import pytest

# lib.* を import できるようにする(各テストファイルで個別に sys.path.insert していた
# ものを1箇所に集約した)。
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--transcript",
        action="store",
        default=os.environ.get("SEMANTICA_TRACE_TEST_TRANSCRIPT"),
        help="実データで検査する親セッションの transcript(.jsonl)。指定が無ければ"
        "実データ依存のテストは skip する。",
    )
    parser.addoption(
        "--subagent-transcript",
        action="store",
        default=os.environ.get("SEMANTICA_TRACE_TEST_SUBAGENT_TRANSCRIPT"),
        help="実データで検査するサブエージェント transcript"
        "(<session>/subagents/agent-<id>.jsonl)。指定が無ければ skip する。",
    )


@pytest.fixture
def real_transcript(request: pytest.FixtureRequest) -> str:
    path = request.config.getoption("--transcript")
    if not path:
        pytest.skip(
            "実 transcript が指定されていない。--transcript <path> か "
            "SEMANTICA_TRACE_TEST_TRANSCRIPT で渡す。"
        )
    if not os.path.exists(path):
        pytest.skip(f"指定された transcript が存在しない: {path}")
    return path


@pytest.fixture
def real_subagent_transcript(request: pytest.FixtureRequest) -> str:
    path = request.config.getoption("--subagent-transcript")
    if not path:
        pytest.skip(
            "実サブエージェント transcript が指定されていない。"
            "--subagent-transcript <path> か SEMANTICA_TRACE_TEST_SUBAGENT_TRANSCRIPT で渡す。"
        )
    if not os.path.exists(path):
        pytest.skip(f"指定された transcript が存在しない: {path}")
    return path
