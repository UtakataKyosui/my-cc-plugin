#!/usr/bin/env python3
"""
PostToolUse (Edit/Write) hook: ソースファイル変更後にテスト充足状況を確認する

- 全対応言語のソースファイルを対象（UI コンポーネントに限定しない）
- 対応するテストファイルが存在しない場合に警告を出力する
- テストファイルが存在する場合は cyclomatic complexity ベースの充足確認も行う
- 常に exit 0（絶対にブロックしない）
- 外部依存なし（stdlib のみ）
"""

import contextlib
import importlib.util
import json
import os
import sys


def _load_check_module():
    """check-test-exists.py の関数を動的にインポートする"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    module_path = os.path.join(script_dir, "check-test-exists.py")
    spec = importlib.util.spec_from_file_location("check_test_exists", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module from {module_path}")
    mod = importlib.util.module_from_spec(spec)
    with contextlib.suppress(SystemExit):
        spec.loader.exec_module(mod)
    return mod


# check-test-exists.py から共通関数をインポート
try:
    _check = _load_check_module()
    _is_source_code = _check.is_source_code
    _is_excluded_file = _check.is_excluded_file
    _is_test_file = _check.is_test_file
    _find_test_file = _check.find_test_file
    _count_branch_keywords = _check.count_branch_keywords
    _count_test_functions = _check.count_test_functions
    _LOADED = True
except Exception as e:
    print(
        f"[tdd-enforce] ⚠️ check-test-exists.py のロードに失敗しました: {e}",
        file=sys.stderr,
    )
    _LOADED = False


def main():
    try:
        data = json.loads(sys.stdin.read())
    except (json.JSONDecodeError, EOFError, ValueError):
        sys.exit(0)

    if not _LOADED:
        # フォールバック: チェックをスキップ
        sys.exit(0)

    try:
        tool_input = data.get("tool_input", {})
        file_path = tool_input.get("file_path") or tool_input.get("path", "")

        if not file_path:
            sys.exit(0)

        # ソースコードでなければスキップ
        if not _is_source_code(file_path):
            sys.exit(0)

        # 除外ファイルはスキップ
        if _is_excluded_file(file_path):
            sys.exit(0)

        # テストファイル自体はスキップ
        if _is_test_file(file_path):
            sys.exit(0)

        # ファイルが実在するか確認（削除操作などは除外）
        if not os.path.isfile(file_path):
            sys.exit(0)

        basename = os.path.basename(file_path)
        ext = os.path.splitext(file_path)[1].lower()

        test_file: str | None = _find_test_file(file_path)

        if test_file is None or (test_file == file_path and ext != ".rs"):
            print(
                f"[tdd-enforce] ⚠️  テストファイルが見つかりません: {basename}",
                file=sys.stderr,
            )
            print(
                f"  対象: {file_path}",
                file=sys.stderr,
            )
            if ext in (".tsx", ".jsx", ".vue", ".svelte"):
                print(
                    "  tdd-enforce:ui-coverage-analyze スキルで"
                    "カバレッジギャップを分析できます。",
                    file=sys.stderr,
                )
            else:
                print(
                    "  /issue-driven-flow:tdd-cycle コマンドで"
                    " TDD サイクルを開始できます。",
                    file=sys.stderr,
                )
            sys.exit(0)

        # テストファイルが存在する場合: cyclomatic complexity ベースの充足確認
        cc = _count_branch_keywords(file_path)
        min_tests = cc + 1
        actual = _count_test_functions(test_file, ext)

        if actual == 0:
            print(
                f"[tdd-enforce] ⚠️  テスト関数が見つかりません: {basename}",
                file=sys.stderr,
            )
            print(
                f"  テストファイル: {test_file}",
                file=sys.stderr,
            )
            print(
                "  テストファイルは存在しますが、テスト関数が定義されていません。",
                file=sys.stderr,
            )
        elif actual < min_tests:
            ratio = int(actual / min_tests * 100)
            print(
                f"[tdd-enforce] ⚠️  テストが不足しています: {basename} "
                f"({actual}/{min_tests} 件, {ratio}%)",
                file=sys.stderr,
            )
            print(
                f"  分岐キーワード数: {cc} → 推奨最低テスト数: {min_tests} 件",
                file=sys.stderr,
            )
            print(
                "  正常系・異常系・境界値のテストを追加してください。",
                file=sys.stderr,
            )

    except Exception as e:
        print(f"[tdd-enforce] 予期しないエラー: {e}", file=sys.stderr)

    sys.exit(0)


if __name__ == "__main__":
    main()
