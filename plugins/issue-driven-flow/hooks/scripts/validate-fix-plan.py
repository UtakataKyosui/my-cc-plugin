#!/usr/bin/env python3
"""SubagentStop hook: review-fixer が出力する fix-plan.json のスキーマを検証する。

fix-plan.json は /tmp/review-fix-plan-<PR番号>.json に書き出される。
ファイルが存在しない場合は正常終了（agent が修正不要と判断した可能性）。
"""

import glob
import json
import os
import sys
import tempfile

REQUIRED_KEYS = {"thread_id", "summary", "files", "commit_message"}


def validate_fix_plan(path: str) -> list[str]:
    errors: list[str] = []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        return [f"fix-plan.json を読み取れません: {e}"]
    except json.JSONDecodeError as e:
        return [f"JSON パースエラー: {e}"]

    if not isinstance(data, list):
        return ["fix-plan.json はリスト形式である必要があります"]

    for i, entry in enumerate(data):
        if not isinstance(entry, dict):
            errors.append(f"entry[{i}]: dict 形式ではありません")
            continue
        missing = REQUIRED_KEYS - entry.keys()
        if missing:
            errors.append(f"entry[{i}]: 必須キーが不足しています — {missing}")
        if "files" in entry and not isinstance(entry["files"], list):
            errors.append(f"entry[{i}]: files はリスト形式である必要があります")

    return errors


def main() -> None:
    # 一時ディレクトリ以下の fix-plan JSON を検索
    tmpdir = tempfile.gettempdir()
    candidates = glob.glob(os.path.join(tmpdir, "review-fix-plan-*.json"))
    if not candidates:
        # ファイルなし = エージェントが修正対象なしと判断
        sys.exit(0)

    all_errors: list[str] = []
    for path in candidates:
        errors = validate_fix_plan(path)
        for err in errors:
            all_errors.append(f"{path}: {err}")

    if all_errors:
        print("[auto-pr-responder] fix-plan.json スキーマエラー:", file=sys.stderr)
        for err in all_errors:
            print(f"  - {err}", file=sys.stderr)
        # 警告のみ（exit 0）。修正計画の問題は呼び出し元が対処する
    else:
        candidates_str = ", ".join(candidates)
        print(f"[auto-pr-responder] fix-plan.json 検証: OK ({candidates_str})")

    sys.exit(0)


if __name__ == "__main__":
    main()
