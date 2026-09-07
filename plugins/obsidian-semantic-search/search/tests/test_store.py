"""store モジュールのテスト（embeddings.npy / chunks.jsonl / manifest.json の I/O）。

numpy が必要。venv 内で実行する（setup.sh 後）。
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from obsidian_semantic_search.store import IndexStore  # noqa: E402


class IndexStoreTest(unittest.TestCase):
    def test_exists_false_before_save(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = IndexStore(Path(d) / "idx")
            self.assertFalse(store.exists())

    def test_save_then_load_roundtrip(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = IndexStore(Path(d) / "idx")
            emb = np.array([[1.0, 0.0], [0.0, 1.0]], dtype=np.float32)
            chunks = [
                {"id": "a#0", "path": "a.md", "title": "A", "heading": "", "line_start": 1, "text": "x"},
                {"id": "b#0", "path": "b.md", "title": "B", "heading": "S", "line_start": 3, "text": "y"},
            ]
            manifest = {"model": "m", "dim": 2, "files": {}}
            store.save(emb, chunks, manifest)

            self.assertTrue(store.exists())
            emb2, chunks2, manifest2 = store.load()
            np.testing.assert_array_almost_equal(emb2, emb)
            self.assertEqual(chunks2, chunks)
            self.assertEqual(manifest2["model"], "m")
            self.assertEqual(manifest2["dim"], 2)

    def test_save_overwrites_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            store = IndexStore(Path(d) / "idx")
            store.save(
                np.zeros((1, 2), dtype=np.float32),
                [{"id": "a#0"}],
                {"model": "m", "dim": 2},
            )
            store.save(
                np.ones((1, 2), dtype=np.float32),
                [{"id": "b#0"}],
                {"model": "m", "dim": 2},
            )
            emb2, chunks2, _ = store.load()
            self.assertEqual(chunks2[0]["id"], "b#0")
            np.testing.assert_array_almost_equal(emb2, np.ones((1, 2), dtype=np.float32))


if __name__ == "__main__":
    unittest.main()
