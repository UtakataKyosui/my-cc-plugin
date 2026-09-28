#!/usr/bin/env python3
"""定例の進捗報告を検査せずにクリップボードへ入れるのを止める PreToolUse フック。

standup-progress-note Skill の SKILL.md フロントマターから登録される。検査を
素通りする経路をふさぐ。対象は、クリップボードへ流すコマンドを実行位置で呼び、
かつ standup を含む Bash コマンドに限る。それ以外は何もせず終了する。
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

_PLUGIN_ROOT = os.environ.get("CLAUDE_PLUGIN_ROOT")
SCRIPT = (
    Path(_PLUGIN_ROOT) / "skills/standup-progress-note/scripts/standup.py"
    if _PLUGIN_ROOT
    else Path(__file__).resolve().parent / "standup.py"
)
# 実行位置にあるものだけを拾う。ファイル名やコード中の語に反応させない。
CLIPBOARD_CALL = re.compile(r"(?:^|[\n|;&])\s*(?:[\w./-]*/)?pbcopy(?=\s|$|<)")
REDIRECT = re.compile(r"pbcopy\s*<\s*([^\s;|&<>]+)")


def block(message: str) -> None:
    print(message, file=sys.stderr)
    sys.exit(2)


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    command = payload.get("tool_input", {}).get("command", "")
    if "standup" not in command or not CLIPBOARD_CALL.search(command):
        return 0
    if not SCRIPT.exists():
        return 0

    match = REDIRECT.search(command)
    if not match:
        block(
            "進捗報告は標準入力から直接 pbcopy せず、ファイルに書いてから次を実行する。\n"
            f"  python3 {SCRIPT} copy /tmp/standup-<日付>.txt"
        )

    path = os.path.expandvars(os.path.expanduser(match.group(1).strip("'\"")))
    if not Path(path).is_file():
        return 0

    result = subprocess.run(
        [sys.executable, str(SCRIPT), "validate", path],
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        block(
            "検査は通っているが、コピーは standup.py 経由で行う。\n"
            f"  python3 {SCRIPT} copy {path}"
        )
    block(
        "進捗報告が standup-progress-note の検査を通っていない。\n"
        + result.stdout
        + result.stderr
        + f"\n直してから次を実行する。\n  python3 {SCRIPT} copy {path}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
