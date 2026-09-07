#!/usr/bin/env python3
"""
PR レビュー投稿ヘルパー

正しいフォーマット(適正な実装・修正することが望ましいところ)で PR レビューを投稿する。

使い方:
  # フォーマット検証のみ(stdin から JSON を受け取る)
  echo '{"body": "..."}' | python3 post_review.py --validate-only

  # 投稿(stdin から JSON を受け取る)
  python3 post_review.py --repo owner/repo --pr 123 < review.json

  # インタラクティブモード(対話形式で body を作成して投稿)
  python3 post_review.py --repo owner/repo --pr 123 --interactive
"""

import argparse
import json
import re
import subprocess
import sys
from typing import Any

REQUIRED_SECTIONS = {
    "適正な実装": [r"適正な実装", r"good\s+point", r"## good"],
    "修正することが望ましいところ": [
        r"修正することが望ましい",
        r"must\s+fix",
        r"should\s+fix",
        r"## must",
    ],
}


def check_body(body: str) -> list[str]:
    missing = []
    for section, patterns in REQUIRED_SECTIONS.items():
        if not any(re.search(p, body, re.IGNORECASE) for p in patterns):
            missing.append(section)
    return missing


def validate_review(data: dict[str, Any]) -> list[str]:
    """レビューデータを検証して問題点のリストを返す"""
    errors = []

    body = data.get("body", "")
    if not body:
        errors.append("body が空です")
        return errors

    missing = check_body(body)
    if missing:
        for s in missing:
            errors.append(f"body に「{s}」セクションがありません")

    for i, comment in enumerate(data.get("comments", [])):
        if not isinstance(comment, dict):
            errors.append(f"comments[{i}] が dict ではありません")
            continue
        if not comment.get("body"):
            errors.append(f"comments[{i}] の body が空です")

    return errors


_FIX_SECTION = "## 修正することが望ましいところ"
_NO_ITEMS = {"- なし", "なし"}


def determine_event(body: str) -> str:
    """修正セクションの内容から event を決定する。

    修正項目が空または「なし」なら APPROVE、それ以外は REQUEST_CHANGES。
    """
    m = re.search(
        rf"{re.escape(_FIX_SECTION)}\s*\n(.*?)(?:\n## |\Z)",
        body,
        re.DOTALL,
    )
    if m and m.group(1).strip() in _NO_ITEMS:
        return "APPROVE"
    return "REQUEST_CHANGES"


def build_body_interactive() -> tuple[str, str]:
    """対話形式で body と event を構築する"""
    print("=== PR レビュー body を作成します ===\n")

    print("## 適正な実装 を入力してください(空行で終了):")
    good_points = []
    while True:
        line = input("  - ")
        if not line:
            break
        good_points.append(f"- {line}")

    print("\n## 修正することが望ましいところ を入力してください(空行で終了):")
    fix_points = []
    while True:
        line = input("  - ")
        if not line:
            break
        fix_points.append(f"- {line}")

    good_text = "\n".join(good_points) if good_points else "- なし"
    fix_text = "\n".join(fix_points) if fix_points else "- なし"

    body = f"## 適正な実装\n\n{good_text}\n\n{_FIX_SECTION}\n\n{fix_text}"
    event = determine_event(body)
    return body, event


def post_review(repo: str, pr: int, data: dict[str, Any]) -> None:
    """gh api を呼んでレビューを投稿する"""
    api_path = f"repos/{repo}/pulls/{pr}/reviews"
    json_input = json.dumps(data, ensure_ascii=False)

    result = subprocess.run(  # noqa: S603
        ["gh", "api", api_path, "--method", "POST", "--input", "-"],  # noqa: S607
        input=json_input,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print(f"[エラー] レビュー投稿に失敗しました:\n{result.stderr}", file=sys.stderr)
        sys.exit(1)

    response = json.loads(result.stdout)
    print(f"[完了] レビューを投稿しました (id: {response.get('id', 'unknown')})")
    print(f"  URL: {response.get('html_url', '')}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="PR レビューを正しいフォーマットで投稿する"
    )
    parser.add_argument("--repo", help="リポジトリ(例: owner/repo)")
    parser.add_argument("--pr", type=int, help="PR 番号")
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="フォーマット検証のみ(投稿しない)",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="インタラクティブモードで body を作成",
    )
    args = parser.parse_args()

    if args.interactive:
        if not args.repo or not args.pr:
            print(
                "[エラー] --interactive モードでは --repo と --pr が必要です",
                file=sys.stderr,
            )
            sys.exit(1)

        body, event = build_body_interactive()
        data: dict[str, Any] = {"body": body, "event": event, "comments": []}

        errors = validate_review(data)
        if errors:
            for e in errors:
                print(f"[エラー] {e}", file=sys.stderr)
            sys.exit(1)

        print(f"\n投稿内容:\n{json.dumps(data, ensure_ascii=False, indent=2)}\n")
        confirm = input("投稿しますか? [y/N]: ")
        if confirm.lower() != "y":
            print("キャンセルしました")
            sys.exit(0)

        post_review(args.repo, args.pr, data)
        return

    # stdin から JSON を読む
    if sys.stdin.isatty():
        print(
            "[エラー] stdin から JSON を入力するか"
            "、--interactive モードを使用してください",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        raw = sys.stdin.read()
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[エラー] JSON のパースに失敗しました: {e}", file=sys.stderr)
        sys.exit(1)

    errors = validate_review(data)
    if errors:
        for e in errors:
            print(f"[エラー] {e}", file=sys.stderr)
        sys.exit(1)

    # event を body の内容から自動決定（明示指定がある場合はそちらを優先）
    if data.get("event") not in ("APPROVE", "REQUEST_CHANGES"):
        data["event"] = determine_event(data.get("body", ""))

    if args.validate_only:
        print("[OK] フォーマットは正しいです")
        sys.exit(0)

    if not args.repo or not args.pr:
        print("[エラー] 投稿には --repo と --pr が必要です", file=sys.stderr)
        sys.exit(1)

    post_review(args.repo, args.pr, data)


if __name__ == "__main__":
    main()
