"""indexer モジュールのテスト（走査・増分差分・インデックス構築）。

numpy が必要。埋め込みは fake embed_fn を注入し、実モデルを読み込まない。
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from obsidian_semantic_search import indexer  # noqa: E402
from obsidian_semantic_search.store import IndexStore  # noqa: E402


def _fake_embed(texts, *, is_query=False):
    """テキスト長に依存した決定的なダミー埋め込み（2次元・L2正規化）。"""
    vecs = []
    for t in texts:
        v = np.array([len(t) % 7 + 1, len(t) % 5 + 1], dtype=np.float32)
        v /= np.linalg.norm(v)
        vecs.append(v)
    return np.vstack(vecs).astype(np.float32)


class ScanFilesTest(unittest.TestCase):
    def test_finds_markdown_and_excludes_noise(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "knowledge").mkdir()
            (root / "knowledge" / "a.md").write_text("# A\nbody\n", encoding="utf-8")
            (root / "node_modules").mkdir()
            (root / "node_modules" / "b.md").write_text("x", encoding="utf-8")
            (root / ".obsidian").mkdir()
            (root / ".obsidian" / "c.md").write_text("x", encoding="utf-8")

            scanned = indexer.scan_files(root)
            self.assertIn("knowledge/a.md", scanned)
            self.assertNotIn("node_modules/b.md", scanned)
            self.assertNotIn(".obsidian/c.md", scanned)

    def test_os_walk_does_not_descend_into_excluded_dirs(self) -> None:
        # os.walk で dirnames を剪定しているため、除外ディレクトリ配下の
        # ファイルは scanned に一切含まれない（in-place 剪定の動作確認）。
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            deep = root / "node_modules" / "a" / "b" / "c"
            deep.mkdir(parents=True)
            (deep / "deep.md").write_text("# Deep\nsome content.\n", encoding="utf-8")
            (root / "note.md").write_text("# Note\nbody here.\n", encoding="utf-8")

            scanned = indexer.scan_files(root)
            self.assertIn("note.md", scanned)
            # node_modules 配下は再帰的に降りないので deep.md も含まれない
            self.assertFalse(any("deep.md" in k for k in scanned))


class DiffManifestTest(unittest.TestCase):
    def test_detects_changed_new_and_deleted(self) -> None:
        old = {
            "files": {
                "same.md": {"mtime": 1.0, "size": 10},
                "changed.md": {"mtime": 1.0, "size": 10},
                "deleted.md": {"mtime": 1.0, "size": 10},
            }
        }
        scanned = {
            "same.md": {"mtime": 1.0, "size": 10},
            "changed.md": {"mtime": 2.0, "size": 12},
            "new.md": {"mtime": 3.0, "size": 5},
        }
        to_index, to_delete = indexer.diff_manifest(old, scanned)
        self.assertEqual(to_index, {"changed.md", "new.md"})
        self.assertEqual(to_delete, {"deleted.md"})


class BuildIndexTest(unittest.TestCase):
    def test_builds_store_with_fake_embedder(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "knowledge").mkdir()
            (root / "knowledge" / "a.md").write_text(
                "# A\nsome content long enough to chunk.\n", encoding="utf-8"
            )
            index_dir = root / ".idx"
            summary = indexer.build_index(
                root, index_dir, model_name="fake", full=True, embed_fn=_fake_embed
            )
            self.assertGreaterEqual(summary["files"], 1)
            self.assertGreaterEqual(summary["chunks"], 1)
            self.assertTrue(IndexStore(index_dir).exists())

    def test_incremental_skips_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "a.md").write_text("# A\ncontent long enough here.\n", encoding="utf-8")
            index_dir = root / ".idx"
            indexer.build_index(root, index_dir, "fake", full=True, embed_fn=_fake_embed)
            summary = indexer.build_index(root, index_dir, "fake", full=False, embed_fn=_fake_embed)
            self.assertEqual(summary["reindexed"], 0)
            self.assertTrue(summary["up_to_date"])


if __name__ == "__main__":
    unittest.main()
