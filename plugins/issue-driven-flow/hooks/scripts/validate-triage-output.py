#!/usr/bin/env python3
"""SubagentStop hook: pr-triage が出力する JSON のスキーマを検証する。

出力は /tmp/pr-triage-<PR番号>.json に書き出される。
ファイルが存在しない場合は正常終了（triage agent が分類対象なしと判断した可能性）。
"""

import glob
import json
import os
import sys
import tempfile

VALID_CATEGORIES = {"valid-fix", "invalid-reject", "needs-human"}
REQUIRED_RESULT_KEYS = {"thread_id", "category", "reason", "reply_draft"}


def validate_triage(path: str) -> list[str]:
    errors: list[str] = []
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except OSError as e:
        return [f"ファイルを読み取れません: {e}"]
    except json.JSONDecodeError as e:
        return [f"JSON パースエラー: {e}"]

    if not isinstance(data, dict):
        return ["トップレベルは dict 形式である必要があります"]

    results = data.get("results", [])
    if not isinstance(results, list):
        return ["results はリスト形式である必要があります"]

    for i, entry in enumerate(results):
        if not isinstance(entry, dict):
            errors.append(f"results[{i}]: dict 形式ではありません")
            continue

        missing = REQUIRED_RESULT_KEYS - entry.keys()
        if missing:
            errors.append(f"results[{i}]: 必須キーが不足 — {missing}")

        category = entry.get("category")
        if category not in VALID_CATEGORIES:
            errors.append(
                f"results[{i}]: category が不正 — '{category}' "
                f"(有効値: {VALID_CATEGORIES})"
            )

        # valid-fix には fix_plan が必須
        if category == "valid-fix" and "fix_plan" not in entry:
            errors.append(f"results[{i}]: valid-fix には fix_plan が必要です")

        if "fix_plan" in entry:
            fp = entry["fix_plan"]
            if not isinstance(fp, dict):
                errors.append(
                    f"results[{i}]: fix_plan は dict 形式である必要があります"
                )
            else:
                for key in ("files", "summary", "commit_message"):
                    if key not in fp:
                        errors.append(f"results[{i}]: fix_plan.{key} が不足しています")

    return errors


def main() -> None:
    tmpdir = tempfile.gettempdir()
    candidates = glob.glob(os.path.join(tmpdir, "pr-triage-*.json"))
    if not candidates:
        # ファイルなし = triage 対象なし、正常終了
        sys.exit(0)

    all_errors: list[str] = []
    for path in candidates:
        errors = validate_triage(path)
        for err in errors:
            all_errors.append(f"{path}: {err}")

    if all_errors:
        print("[auto-pr-responder] triage JSON スキーマエラー:", file=sys.stderr)
        for err in all_errors:
            print(f"  - {err}", file=sys.stderr)
        # 警告のみ（exit 0）
    else:
        candidates_str = ", ".join(candidates)
        print(f"[auto-pr-responder] triage JSON 検証: OK ({candidates_str})")

    sys.exit(0)


if __name__ == "__main__":
    main()
