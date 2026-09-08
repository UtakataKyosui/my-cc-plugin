"""Keep the duplicated workflow agents aligned with change-driven's canonical copy."""

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[3]
CANONICAL = ROOT / "plugins" / "change-driven"
CONSUMER = ROOT / "plugins" / "issue-driven-flow"


class AgentSyncTest(unittest.TestCase):
    def test_change_planner_is_synced(self):
        self.assertEqual(
            (CANONICAL / "agents" / "change-planner.md").read_bytes(),
            (CONSUMER / "agents" / "change-planner.md").read_bytes(),
        )

    def test_commit_writer_is_synced(self):
        self.assertEqual(
            (CANONICAL / "agents" / "conventional-commit-writer.md").read_bytes(),
            (CONSUMER / "agents" / "conventional-commit-writer.md").read_bytes(),
        )

    def test_scope_resolver_is_synced(self):
        self.assertEqual(
            (CANONICAL / "scripts" / "scope-manifest-path.sh").read_bytes(),
            (CONSUMER / "scripts" / "scope-manifest-path.sh").read_bytes(),
        )


if __name__ == "__main__":
    unittest.main()
