import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import create_myzenns_issue as target


class CreateIssueTests(unittest.TestCase):
    def test_requires_confirmation(self):
        with tempfile.TemporaryDirectory() as directory:
            body = Path(directory) / "body.md"
            body.write_text("body", encoding="utf-8")
            self.assertEqual(
                target.main(["--repo", "owner/repo", "--title", "title", "--body-file", str(body)]),
                2,
            )

    @patch("create_myzenns_issue.run_gh")
    def test_checks_labels_before_creating(self, run_gh):
        run_gh.return_value.returncode = 0
        run_gh.return_value.stdout = '[{"name": "zenn"}]'
        run_gh.return_value.stderr = ""
        with tempfile.TemporaryDirectory() as directory:
            body = Path(directory) / "body.md"
            body.write_text("body", encoding="utf-8")
            self.assertEqual(
                target.main([
                    "--repo", "owner/repo", "--title", "title",
                    "--body-file", str(body), "--confirmed",
                ]),
                2,
            )
        self.assertEqual(run_gh.call_count, 1)

    @patch("create_myzenns_issue.run_gh")
    def test_creates_issue_after_confirmation(self, run_gh):
        label_result = type("Result", (), {"returncode": 0, "stdout": '[{"name": "zenn"}, {"name": "article"}]', "stderr": ""})()
        issue_result = type("Result", (), {"returncode": 0, "stdout": "https://github.com/owner/repo/issues/1\n", "stderr": ""})()
        run_gh.side_effect = [label_result, issue_result]
        with tempfile.TemporaryDirectory() as directory:
            body = Path(directory) / "body.md"
            body.write_text("body", encoding="utf-8")
            self.assertEqual(
                target.main([
                    "--repo", "owner/repo", "--title", "title",
                    "--body-file", str(body), "--confirmed",
                ]),
                0,
            )
        self.assertEqual(run_gh.call_count, 2)


if __name__ == "__main__":
    unittest.main()
