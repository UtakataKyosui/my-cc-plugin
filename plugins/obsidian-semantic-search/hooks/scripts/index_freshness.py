#!/usr/bin/env python3
"""SessionStart hook: 意味検索インデックスの鮮度をチェックする。

`bin/oss status --json` を短タイムアウトで実行し、インデックスが未構築または
陳腐化していれば 1-2 行の注記を additionalContext に注入する。最新なら何も出さない。

重い再インデックスはここでは絶対に行わない（セッション起動を遅延させない）。
status はモデルを読み込まないため軽量。失敗時は黙って exit 0（非ブロッキング）。
"""

import json
import os
import subprocess
import sys

STATUS_TIMEOUT = 8  # 秒


def build_notice(status: dict) -> str | None:
    """status dict から注記文字列を生成する。最新なら None。"""
    if status.get("missing_index"):
        return (
            "意味検索インデックスが未構築です。`/obsidian-semantic-search` の"
            "初回セットアップ（setup.sh 実行 + index 構築）を行ってください。"
        )
    stale = status.get("stale", 0)
    if stale and stale > 0:
        return (
            f"意味検索インデックスが {stale} 件未更新です。"
            "必要なら obsidian-semantic-search で index を更新してください。"
        )
    return None


def _plugin_root() -> str:
    root = os.environ.get("CLAUDE_PLUGIN_ROOT")
    if root:
        return root
    # hooks/scripts/ から2階層上がプラグインルート
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _fetch_status() -> dict | None:
    oss = os.path.join(_plugin_root(), "bin", "oss")
    if not os.path.isfile(oss):
        return None
    try:
        result = subprocess.run(  # noqa: S603
            [oss, "status", "--json"],
            capture_output=True,
            text=True,
            timeout=STATUS_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if result.returncode != 0 or not result.stdout.strip():
        return None
    try:
        return json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return None


def main() -> None:
    try:
        # stdin は読み捨て（SessionStart の入力は使わない）
        try:
            sys.stdin.read()
        except (OSError, ValueError):
            pass

        status = _fetch_status()
        if not status:
            sys.exit(0)

        notice = build_notice(status)
        if notice:
            print(
                json.dumps(
                    {
                        "hookSpecificOutput": {
                            "hookEventName": "SessionStart",
                            "additionalContext": f"<!-- obsidian-semantic-search -->\n{notice}",
                        }
                    },
                    ensure_ascii=False,
                )
            )
        sys.exit(0)
    except Exception as exc:  # noqa: BLE001
        print(f"[index-freshness] unexpected error: {exc}", file=sys.stderr)
        sys.exit(0)


if __name__ == "__main__":
    main()
