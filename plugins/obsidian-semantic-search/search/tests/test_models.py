"""models モジュールのテスト（モデルごとの query/passage プレフィックス）。

load_model は重い埋め込みモデルを読み込むためここでは検証せず、
プレフィックスのレジストリ（純粋関数）のみを対象とする。
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from obsidian_semantic_search import models  # noqa: E402


class PrefixTest(unittest.TestCase):
    def test_e5_query_prefix(self) -> None:
        self.assertEqual(
            models.query_prefix("intfloat/multilingual-e5-small"), "query: "
        )

    def test_e5_passage_prefix(self) -> None:
        self.assertEqual(
            models.passage_prefix("intfloat/multilingual-e5-small"), "passage: "
        )

    def test_unknown_model_has_empty_prefix(self) -> None:
        self.assertEqual(models.query_prefix("vendor/unknown"), "")
        self.assertEqual(models.passage_prefix("vendor/unknown"), "")

    def test_registry_entries_are_pairs(self) -> None:
        for name, value in models.MODEL_PREFIXES.items():
            self.assertIsInstance(name, str)
            self.assertEqual(len(value), 2)


if __name__ == "__main__":
    unittest.main()
