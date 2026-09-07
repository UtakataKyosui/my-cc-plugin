#!/usr/bin/env python3
"""
レビューコマンドのフォーマット検証

stdin からシェルコマンド文字列を受け取り、gh api reviews 投稿の
body に必須セクションが含まれているか検証する。

Exit codes:
  0: OK（または検証不可のため advisory のみ）
  2: フォーマットエラー（body に必須セクションが欠落）
"""

import json
import re
import shlex
import sys

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
    """body に欠落している必須セクションを返す"""
    missing = []
    for section, patterns in REQUIRED_SECTIONS.items():
        if not any(re.search(p, body, re.IGNORECASE) for p in patterns):
            missing.append(f"「{section}」")
    return missing


def extract_body_from_heredoc(command: str) -> str | None:
    """heredoc パターン (<<EOF, <<'EOF', <<"EOF", <<-EOF 等) から body を返す"""
    pattern = (
        r"<<-?\s*['\"]?(?P<delim>[a-zA-Z0-9_]+)['\"]?\s*\n"
        r"(.*?)\n\s*(?P=delim)(?:\s|$)"
    )
    m = re.search(pattern, command, re.DOTALL | re.MULTILINE)
    if not m:
        return None
    try:
        data = json.loads(m.group(2).strip())
        return data.get("body", "")
    except (json.JSONDecodeError, AttributeError):
        return None


def extract_body_from_field(command: str) -> str | None:
    """'-f body=...' パターンから body を返す (shlex でクォート処理)"""
    try:
        tokens = shlex.split(command)
    except ValueError:
        return None
    for i, token in enumerate(tokens):
        if token in ("-f", "-F") and i + 1 < len(tokens):
            next_token = tokens[i + 1]
            if next_token.startswith("body="):
                return next_token[5:]
    return None


def main() -> None:
    command = sys.stdin.read()

    # gh api .../reviews の呼び出しかどうか
    if not re.search(r"gh\s+api\s+.*pulls/\d+/reviews", command):
        sys.exit(0)

    # body を抽出（heredoc → -f body= の順に試みる）
    body = extract_body_from_heredoc(command) or extract_body_from_field(command)

    if body is None:
        # 抽出できない場合は advisory のみ（ブロックしない）
        print(
            "[pr-review-format] レビューを投稿しようとしています。\n"
            "body に以下の両セクションが含まれているか確認してください:\n"
            "  ## 適正な実装\n"
            "  ## 修正することが望ましいところ",
            file=sys.stderr,
        )
        sys.exit(0)

    missing = check_body(body)
    if missing:
        sections = "、".join(missing)
        msg = "レビューの body に必須セクションがありません"
        header = f"[pr-review-format] {msg}: {sections}"
        print(
            f"{header}\n\n"
            "正しい形式:\n"
            "  ## 適正な実装\n"
            "  - ...\n\n"
            "  ## 修正することが望ましいところ\n"
            "  - ...",
            file=sys.stderr,
        )
        sys.exit(2)

    sys.exit(0)


if __name__ == "__main__":
    main()
