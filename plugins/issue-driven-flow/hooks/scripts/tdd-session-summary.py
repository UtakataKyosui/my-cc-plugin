#!/usr/bin/env python3
"""
Stop hook: セッション終了時にテスト/ソースファイル比率のサマリーを表示する

- 作業ディレクトリ内のテストファイルとソースファイルの比率を集計
- 常に exit 0（絶対にブロックしない）
- 外部依存なし（stdlib のみ）
"""

import json
import os
import re
import sys

SOURCE_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".go",
    ".rb",
    ".ex",
    ".swift",
    ".kt",
}
TEST_PATTERNS = re.compile(
    r"(test_|_test\.|\.test\.|\.spec\.|_spec\.|tests?/|__tests__/|spec/)",
    re.IGNORECASE,
)

# Cargo.toml インラインテストを考慮する Rust ファイル
RUST_INLINE_TEST_PATTERN = re.compile(r"#\[cfg\(test\)\]")

MAX_WALK_FILES = 500


def count_files(cwd: str) -> tuple[int, int]:
    """ソースファイル数とテストファイル数を返す（最大 MAX_WALK_FILES ファイルまで）"""
    source_count = 0
    test_count = 0
    total_scanned = 0

    skip_dirs = {
        ".git",
        ".jj",
        "node_modules",
        "target",
        "dist",
        ".venv",
        "__pycache__",
    }

    for root, dirs, files in os.walk(cwd):
        # スキップ対象ディレクトリを除外
        dirs[:] = [d for d in dirs if d not in skip_dirs]

        for fname in files:
            _, ext = os.path.splitext(fname)
            if ext not in SOURCE_EXTENSIONS and ext != ".rs":
                continue

            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, cwd)

            total_scanned += 1
            if total_scanned > MAX_WALK_FILES:
                return source_count, test_count

            if TEST_PATTERNS.search(rel_path):
                test_count += 1
            elif ext == ".rs":
                # Rust: インラインテストを確認
                try:
                    with open(fpath, encoding="utf-8", errors="ignore") as f:
                        content = f.read(8192)  # 先頭 8KB のみ確認
                    if RUST_INLINE_TEST_PATTERN.search(content):
                        test_count += 1
                    else:
                        source_count += 1
                except OSError:
                    source_count += 1
            else:
                source_count += 1

    return source_count, test_count


def main():
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError, ValueError):
        data = {}

    try:
        cwd = data.get("cwd", os.getcwd())
        if not cwd or not os.path.isdir(cwd):
            sys.exit(0)

        source_count, test_count = count_files(cwd)
        total = source_count + test_count

        if total == 0:
            sys.exit(0)

        ratio = (test_count / total * 100) if total > 0 else 0

        print(
            f"[tdd-enforce] セッションサマリー: ソース {source_count} ファイル"
            f" / テスト {test_count} ファイル (テスト比率 {ratio:.0f}%)",
            file=sys.stderr,
        )

        if ratio < 50 and test_count < source_count:
            print(
                "  テスト不足のファイルがあります。"
                "次のセッションでテストを追加してください。",
                file=sys.stderr,
            )

    except Exception as e:
        print(f"[tdd-enforce] 予期しないエラー: {e}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
