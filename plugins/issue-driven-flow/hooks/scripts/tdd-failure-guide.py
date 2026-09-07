#!/usr/bin/env python3
"""
PostToolUseFailure hook (Bash matcher): テスト失敗時に TDD サイクルガイダンスを提示する

- テスト実行コマンドのみ対象（非テストコマンドは早期リターン）
- 常に exit 0（絶対にブロックしない）
- 外部依存なし（stdlib のみ）
"""

import json
import re
import sys

TEST_COMMAND_PATTERNS = [
    r"\bpytest\b",
    r"\bcargo\s+test\b",
    r"\bvitest\b",
    r"\bjest\b",
    r"\bgo\s+test\b",
    r"\bdotnet\s+test\b",
    r"\brspec\b",
    r"\bmix\s+test\b",
    r"\bswift\s+test\b",
    r"\bmocha\b",
    r"\bnpm\s+(run\s+)?test\b",
    r"\bpnpm\s+(run\s+)?test\b",
    r"\byarn\s+test\b",
    r"\bmise\s+(exec\s+--\s+)?.*test\b",
]


def is_test_command(command: str) -> bool:
    return any(re.search(pat, command) for pat in TEST_COMMAND_PATTERNS)


def main():
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)

    try:
        tool_input = data.get("tool_input", {})
        command = tool_input.get("command", "")

        if not command or not is_test_command(command):
            sys.exit(0)

        print(
            "[tdd-enforce] テスト失敗を検出しました（TDD の Red フェーズ）",  # noqa: RUF001
            file=sys.stderr,
        )
        print(
            "  次のステップ: 失敗の原因を確認し、"
            "最小限の実装コードを書いて Green にしてください。",
            file=sys.stderr,
        )
        print(
            "  TDD サイクル: Red（テスト失敗）"  # noqa: RUF001
            "→ Green（テスト通過）→ Refactor（リファクタリング）",  # noqa: RUF001
            file=sys.stderr,
        )

    except Exception as e:
        print(f"[tdd-enforce] 予期しないエラー: {e}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
