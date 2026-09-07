"""__main__ モジュールのテスト（CLI 引数パース・エラーハンドリング）。"""

import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from obsidian_semantic_search import __main__ as main_mod  # noqa: E402
from obsidian_semantic_search.__main__ import build_parser  # noqa: E402


class BuildParserTest(unittest.TestCase):
    def test_status_command(self) -> None:
        args = build_parser().parse_args(["status", "--json"])
        self.assertEqual(args.command, "status")
        self.assertTrue(args.json)

    def test_index_full_flag(self) -> None:
        args = build_parser().parse_args(["index", "--full"])
        self.assertEqual(args.command, "index")
        self.assertTrue(args.full)

    def test_query_args(self) -> None:
        args = build_parser().parse_args(["query", "hello world", "--top-k", "3", "--json"])
        self.assertEqual(args.command, "query")
        self.assertEqual(args.text, "hello world")
        self.assertEqual(args.top_k, 3)
        self.assertTrue(args.json)

    def test_query_default_top_k(self) -> None:
        args = build_parser().parse_args(["query", "x"])
        self.assertEqual(args.top_k, 5)


class IndexErrorHandlingTest(unittest.TestCase):
    def test_index_returns_1_on_value_error_without_traceback(self) -> None:
        # モデル変更等で build_index が ValueError を投げても、生のトレースバックを
        # 出さず exit code 1 で終わる（CLI として grace に失敗する）。
        with mock.patch.object(main_mod, "resolve_vault_dir", return_value="/tmp/v"), \
            mock.patch.object(main_mod, "resolve_index_dir", return_value="/tmp/v/idx"), \
            mock.patch.object(main_mod, "get_model_name", return_value="m"), \
            mock.patch.object(
                main_mod, "build_index", side_effect=ValueError("model changed")
            ):
            rc = main_mod.main(["index"])
        self.assertEqual(rc, 1)


if __name__ == "__main__":
    unittest.main()
