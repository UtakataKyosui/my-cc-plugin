"""search モジュールのテスト（numpy 総当たりランキング・検索）。

numpy が必要。検索は fake embed_fn を注入し、実モデルを読み込まない。
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from obsidian_semantic_search import search as search_mod  # noqa: E402
from obsidian_semantic_search.store import IndexStore  # noqa: E402


class RankTest(unittest.TestCase):
    def test_returns_top_k_in_descending_score(self) -> None:
        emb = np.array(
            [[1.0, 0.0], [0.0, 1.0], [0.7071, 0.7071]], dtype=np.float32
        )
        q = np.array([1.0, 0.0], dtype=np.float32)
        ranked = search_mod.rank(emb, q, top_k=2)
        self.assertEqual(len(ranked), 2)
        self.assertEqual(ranked[0][0], 0)  # 最も近い行 index 0
        self.assertGreaterEqual(ranked[0][1], ranked[1][1])  # スコア降順

    def test_top_k_larger_than_rows(self) -> None:
        emb = np.array([[1.0, 0.0]], dtype=np.float32)
        q = np.array([1.0, 0.0], dtype=np.float32)
        ranked = search_mod.rank(emb, q, top_k=10)
        self.assertEqual(len(ranked), 1)


class SearchTest(unittest.TestCase):
    def _build_store(self, index_dir: Path) -> None:
        emb = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
        chunks = [
            {"id": "a#0", "path": "a.md", "title": "A", "heading": "HA", "line_start": 1, "text": "alpha text"},
            {"id": "b#0", "path": "b.md", "title": "B", "heading": "HB", "line_start": 2, "text": "beta text"},
        ]
        IndexStore(index_dir).save(emb, chunks, {"model": "fake", "dim": 2, "files": {}})

    def test_search_returns_ranked_results(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            index_dir = Path(d) / "idx"
            self._build_store(index_dir)

            def fake_embed(texts, *, is_query=False):
                # クエリは row 0 ([1,0]) に一致させる
                return np.array([[1.0, 0.0]], dtype=np.float32)

            result = search_mod.search(
                "anything", top_k=2, index_dir=index_dir, embed_fn=fake_embed
            )
            self.assertEqual(result["results"][0]["path"], "a.md")
            self.assertEqual(result["results"][0]["heading"], "HA")
            self.assertIn("score", result["results"][0])
            self.assertEqual(len(result["results"]), 2)

    def test_search_missing_index_raises(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(FileNotFoundError):
                search_mod.search(
                    "q", top_k=1, index_dir=Path(d) / "nope", embed_fn=lambda t, **k: None
                )

    def test_search_resolves_index_dir_when_none(self) -> None:
        # index_dir=None の場合、config から自動解決されて IndexStore が正しく動く。
        # Path(None) で TypeError にならないことを確認する。
        with tempfile.TemporaryDirectory() as d:
            index_dir = Path(d) / "idx"
            self._build_store(index_dir)

            def fake_embed(texts, *, is_query=False):
                return np.array([[1.0, 0.0]], dtype=np.float32)

            with mock.patch.object(
                search_mod, "resolve_vault_dir", return_value=Path(d)
            ), mock.patch.object(
                search_mod, "resolve_index_dir", return_value=index_dir
            ):
                result = search_mod.search("anything", top_k=1, embed_fn=fake_embed)
            self.assertEqual(result["results"][0]["path"], "a.md")

    def test_search_raises_on_count_mismatch(self) -> None:
        # 並行 index 等でベクトル行数とチャンク件数がずれた不整合インデックスは
        # IndexError ではなく ValueError で明示的に弾く。
        with tempfile.TemporaryDirectory() as d:
            index_dir = Path(d) / "idx"
            emb = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)  # 2 行
            chunks = [
                {"id": "a#0", "path": "a.md", "heading": "HA", "line_start": 1, "text": "alpha"}
            ]  # 1 件
            IndexStore(index_dir).save(emb, chunks, {"model": "fake", "dim": 2, "files": {}})
            with self.assertRaises(ValueError):
                search_mod.search(
                    "q", top_k=1, index_dir=index_dir, embed_fn=lambda t, **k: None
                )


if __name__ == "__main__":
    unittest.main()
