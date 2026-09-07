"""config モジュールのテスト（環境変数・パス解決・除外判定）。"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from obsidian_semantic_search import config  # noqa: E402


class GetModelNameTest(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = os.environ.pop("OBSIDIAN_SEMANTIC_MODEL", None)

    def tearDown(self) -> None:
        if self._saved is not None:
            os.environ["OBSIDIAN_SEMANTIC_MODEL"] = self._saved
        else:
            os.environ.pop("OBSIDIAN_SEMANTIC_MODEL", None)

    def test_default_model(self) -> None:
        self.assertEqual(config.get_model_name(), config.DEFAULT_MODEL)

    def test_env_override(self) -> None:
        os.environ["OBSIDIAN_SEMANTIC_MODEL"] = "some/other-model"
        self.assertEqual(config.get_model_name(), "some/other-model")


class ResolveIndexDirTest(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = os.environ.pop("OBSIDIAN_SEMANTIC_INDEX_DIR", None)

    def tearDown(self) -> None:
        if self._saved is not None:
            os.environ["OBSIDIAN_SEMANTIC_INDEX_DIR"] = self._saved
        else:
            os.environ.pop("OBSIDIAN_SEMANTIC_INDEX_DIR", None)

    def test_default_under_vault(self) -> None:
        vault = Path("/tmp/some-vault")
        self.assertEqual(
            config.resolve_index_dir(vault), vault / ".obsidian-semantic-index"
        )

    def test_env_override(self) -> None:
        os.environ["OBSIDIAN_SEMANTIC_INDEX_DIR"] = "/tmp/custom-index"
        # 明示パスは expanduser().resolve() で正規化される（macOS の /tmp→/private/tmp 等）
        self.assertEqual(
            config.resolve_index_dir(Path("/tmp/v")),
            Path("/tmp/custom-index").expanduser().resolve(),
        )


class ResolveVaultDirTest(unittest.TestCase):
    def setUp(self) -> None:
        self._saved = {
            k: os.environ.pop(k, None)
            for k in ("OBSIDIAN_SEMANTIC_VAULT_DIR", "OBSIDIAN_VAULT_PATH", "CLAUDE_PLUGIN_ROOT")
        }

    def tearDown(self) -> None:
        for k, v in self._saved.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)

    def test_existing_explicit_env_wins(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            os.environ["OBSIDIAN_SEMANTIC_VAULT_DIR"] = d
            self.assertEqual(config.resolve_vault_dir(), Path(d).resolve())

    def test_nonexistent_explicit_env_falls_back_to_discovery(self) -> None:
        # 実在しない明示パスは無視し、.obsidian 探索にフォールバックする
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d) / "vault"
            (vault / ".obsidian").mkdir(parents=True)
            plugin_root = vault / "plugins" / "p"
            plugin_root.mkdir(parents=True)
            os.environ["OBSIDIAN_SEMANTIC_VAULT_DIR"] = str(vault / "does-not-exist")
            os.environ["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
            self.assertEqual(config.resolve_vault_dir(), vault.resolve())

    def test_borrowed_vault_path_ignored_when_not_a_vault(self) -> None:
        # OBSIDIAN_VAULT_PATH が .obsidian も .md も持たない空ディレクトリを指す場合は
        # 借用設定として信頼せず、.obsidian 探索にフォールバックする
        with tempfile.TemporaryDirectory() as d:
            empty = Path(d) / "empty"
            empty.mkdir()
            vault = Path(d) / "vault"
            (vault / ".obsidian").mkdir(parents=True)
            nested = vault / "plugins" / "p"
            nested.mkdir(parents=True)
            os.environ["OBSIDIAN_VAULT_PATH"] = str(empty)
            os.environ["CLAUDE_PLUGIN_ROOT"] = str(nested)
            self.assertEqual(config.resolve_vault_dir(), vault.resolve())

    def test_borrowed_vault_path_used_when_has_markdown(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d) / "v"
            vault.mkdir()
            (vault / "note.md").write_text("# x\n", encoding="utf-8")
            os.environ["OBSIDIAN_VAULT_PATH"] = str(vault)
            self.assertEqual(config.resolve_vault_dir(), vault.resolve())

    def test_discovery_via_obsidian_marker(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d) / "vault"
            (vault / ".obsidian").mkdir(parents=True)
            nested = vault / "plugins" / "p"
            nested.mkdir(parents=True)
            os.environ["CLAUDE_PLUGIN_ROOT"] = str(nested)
            self.assertEqual(config.resolve_vault_dir(), vault.resolve())


class IsExcludedTest(unittest.TestCase):
    def test_node_modules_excluded(self) -> None:
        self.assertTrue(config.is_excluded(Path("node_modules/foo/bar.md")))

    def test_dotdir_excluded(self) -> None:
        self.assertTrue(config.is_excluded(Path(".obsidian/workspace.md")))

    def test_plugins_dir_excluded(self) -> None:
        self.assertTrue(config.is_excluded(Path("plugins/x/skills/y.md")))

    def test_normal_knowledge_path_kept(self) -> None:
        self.assertFalse(config.is_excluded(Path("knowledge/claude-code/foo.md")))


if __name__ == "__main__":
    unittest.main()
