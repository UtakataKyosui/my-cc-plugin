#!/usr/bin/env python3
"""Claude Code のバージョンアップ後に builtin-commands.json を更新するメンテ用スクリプト。

使い方:
  python3 update_builtin_manifest.py          # 現在の claude --version を確認して出力
  python3 update_builtin_manifest.py --check  # 現在の manifest と差分を表示するだけ
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

MANIFEST_PATH = Path(__file__).parent.parent / "data" / "builtin-commands.json"


def get_claude_version() -> str:
    try:
        result = subprocess.run(
            ["claude", "--version"],  # noqa: S607
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
        version_line = result.stdout.strip().split("\n")[0]
        # "Claude Code X.Y.Z" のようなフォーマットを想定
        parts = version_line.split()
        return parts[-1] if parts else "unknown"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "unknown"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="builtin-commands.json のバージョン情報を更新する"
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="現在の claude --version を確認して manifest の generated 日付と比較する",
    )
    parser.add_argument(
        "--set-version",
        default=None,
        help="manifest の claude_code_min_version を指定バージョンに更新する",
    )
    args = parser.parse_args()

    if not MANIFEST_PATH.exists():
        print(f"ERROR: manifest not found: {MANIFEST_PATH}", file=sys.stderr)
        sys.exit(1)

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    current_version = get_claude_version()

    print(f"Current claude version : {current_version}")
    print(f"Manifest generated     : {manifest.get('generated', 'unknown')}")
    print(
        f"Manifest min_version   : {manifest.get('claude_code_min_version', 'unknown')}"
    )
    print(f"Commands in manifest   : {len(manifest.get('commands', []))}")

    if args.check:
        print(
            "\nNOTE: 新しいコマンドが追加された場合は data/builtin-commands.json を手動で更新してください。"
        )
        print("      公式ドキュメント: https://docs.anthropic.com/en/docs/claude-code")
        return

    if args.set_version:
        from datetime import datetime

        manifest["claude_code_min_version"] = args.set_version
        manifest["generated"] = datetime.now().strftime("%Y-%m-%d")
        MANIFEST_PATH.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        print(f"\nUpdated: claude_code_min_version = {args.set_version}")
        return

    print("\n使い方:")
    print("  --check           バージョン情報を確認する")
    print("  --set-version X.Y.Z  manifest のバージョンを更新する")


if __name__ == "__main__":
    main()
