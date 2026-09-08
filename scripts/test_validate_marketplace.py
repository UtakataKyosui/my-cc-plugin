import json
import tempfile
import unittest
from pathlib import Path

from validate_marketplace import validate


class MarketplaceValidationTests(unittest.TestCase):
    def test_detects_version_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / ".claude-plugin").mkdir()
            plugin = root / "plugins/example/.claude-plugin"
            plugin.mkdir(parents=True)
            (plugin / "plugin.json").write_text(json.dumps({"name": "example", "version": "1.0.0"}), encoding="utf-8")
            (root / ".claude-plugin/marketplace.json").write_text(json.dumps({"plugins": [{"name": "example", "source": "plugins/example", "version": "2.0.0"}]}), encoding="utf-8")
            errors, _ = validate(root)
            self.assertTrue(any("version mismatch" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
