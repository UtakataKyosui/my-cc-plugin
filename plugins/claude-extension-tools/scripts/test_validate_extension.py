import json
import tempfile
import unittest
from pathlib import Path

from validate_extension import validate


class ValidateExtensionTests(unittest.TestCase):
    def test_skill_requires_directory_name_match(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "wrong" / "SKILL.md"
            path.parent.mkdir()
            path.write_text("---\nname: right\ndescription: test\n---\n", encoding="utf-8")
            errors, _ = validate(path)
            self.assertIn("skill name must match its directory name", errors)

    def test_plugin_manifest_is_validated(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / ".claude-plugin/plugin.json"
            manifest.parent.mkdir()
            manifest.write_text(json.dumps({"name": "x", "version": "0.1.0", "description": "x"}), encoding="utf-8")
            errors, warnings = validate(root)
            self.assertEqual(errors, [])
            self.assertEqual(warnings, [])


if __name__ == "__main__":
    unittest.main()
