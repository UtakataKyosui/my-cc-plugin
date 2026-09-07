"""chunker モジュールのテスト（frontmatter 除去・wiki リンク正規化・見出し分割）。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from obsidian_semantic_search import chunker  # noqa: E402


class StripFrontmatterTest(unittest.TestCase):
    def test_removes_yaml_block_and_reports_offset(self) -> None:
        text = "---\nname: foo\ntags: [a]\n---\n# Title\nbody\n"
        body, offset = chunker.strip_frontmatter(text)
        self.assertTrue(body.startswith("# Title"))
        self.assertEqual(offset, 4)  # 4 行（---, name, tags, ---）が除去される

    def test_no_frontmatter_returns_zero_offset(self) -> None:
        text = "# Title\nbody\n"
        body, offset = chunker.strip_frontmatter(text)
        self.assertEqual(body, text)
        self.assertEqual(offset, 0)


class NormalizeWikilinksTest(unittest.TestCase):
    def test_alias_link_keeps_alias(self) -> None:
        self.assertEqual(chunker.normalize_wikilinks("see [[page-a|別名]] here"), "see 別名 here")

    def test_plain_link_keeps_target(self) -> None:
        self.assertEqual(chunker.normalize_wikilinks("see [[page-a]] here"), "see page-a here")

    def test_embed_is_removed(self) -> None:
        self.assertEqual(chunker.normalize_wikilinks("x ![[img.png]] y"), "x  y")


class ChunkTextTest(unittest.TestCase):
    DOC = (
        "# Title H1\n"
        "intro text here that is reasonably long enough to keep.\n"
        "\n"
        "## Section A\n"
        "content A that is long enough to keep around.\n"
        "\n"
        "## Section B\n"
        "content B also kept and long enough.\n"
    )

    def test_splits_into_one_chunk_per_section(self) -> None:
        chunks = chunker.chunk_text(self.DOC, title="MyNote", rel_path="knowledge/x.md")
        self.assertEqual(len(chunks), 3)

    def test_breadcrumb_includes_title_and_ancestor(self) -> None:
        chunks = chunker.chunk_text(self.DOC, title="MyNote", rel_path="knowledge/x.md")
        section_a = next(c for c in chunks if c["heading"] == "Section A")
        self.assertIn("MyNote", section_a["text"])
        self.assertIn("Title H1", section_a["text"])  # 祖先 H1 がパンくずに含まれる

    def test_line_start_points_at_heading(self) -> None:
        chunks = chunker.chunk_text(self.DOC, title="MyNote", rel_path="knowledge/x.md")
        self.assertEqual(chunks[0]["line_start"], 1)  # "# Title H1" は1行目
        section_a = next(c for c in chunks if c["heading"] == "Section A")
        self.assertEqual(section_a["line_start"], 4)

    def test_long_section_is_split(self) -> None:
        body = "あ" * 400
        doc = f"## Big\n{body}\n"
        chunks = chunker.chunk_text(doc, title="N", rel_path="a.md", max_chars=100, overlap=20)
        self.assertGreater(len(chunks), 1)

    def test_chunk_text_never_exceeds_max_chars_with_breadcrumb(self) -> None:
        # パンくず（タイトル + 見出し）が長く本文も長い場合でも、連結後の text が
        # max_chars を超えない（埋め込みモデルの入力上限超過を防ぐ）。
        long_title = "と" * 40
        body = "あ" * 500
        doc = f"## {'い' * 30}\n{body}\n"
        chunks = chunker.chunk_text(
            doc, title=long_title, rel_path="a.md", max_chars=200, overlap=40
        )
        self.assertGreater(len(chunks), 1)
        for c in chunks:
            self.assertLessEqual(len(c["text"]), 200)

    def test_heading_only_sections_are_skipped(self) -> None:
        doc = "# Only Heading\n## Sub\n"
        chunks = chunker.chunk_text(doc, title="N", rel_path="a.md")
        self.assertEqual(chunks, [])

    def test_chunk_ids_are_unique(self) -> None:
        chunks = chunker.chunk_text(self.DOC, title="MyNote", rel_path="knowledge/x.md")
        ids = [c["id"] for c in chunks]
        self.assertEqual(len(ids), len(set(ids)))


if __name__ == "__main__":
    unittest.main()
