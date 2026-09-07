#!/usr/bin/env python3
"""push.py のユニットテスト（stdlib unittest のみ・pytest 不要）

実行方法:
    python3 test_push.py

`get_push_info` の VCS 分岐を検証する。jj は jj-exec-aliases の
`safe-push` alias が設定されていればそれを推奨し、未設定時は素の
`jj git push`（確認後 push）にフォールバックする点を担保する。
"""

import os
import sys
import unittest
from unittest import mock

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

import push  # noqa: E402
from vcs import VCSInfo, VCSType  # noqa: E402


def _jj_info(branch: str | None) -> VCSInfo:
    return VCSInfo(
        vcs_type=VCSType.JJ,
        root_dir="/repo",
        current_branch=branch,
        remote_url="https://example.com/repo.git",
    )


def _git_info(branch: str | None = "feat/2-y") -> VCSInfo:
    return VCSInfo(
        vcs_type=VCSType.GIT,
        root_dir="/repo",
        current_branch=branch,
        remote_url="https://example.com/repo.git",
    )


def _alias_absent() -> mock.Mock:
    """subprocess.run result for `jj config get aliases.safe-push` when unset."""
    return mock.Mock(returncode=1, stdout="")


def _alias_present() -> mock.Mock:
    """subprocess.run result when the jj-exec-aliases safe-push alias is configured."""
    return mock.Mock(returncode=0, stdout='["util", "exec", "--", "jj-safe-push"]\n')


class GetPushInfoJJTest(unittest.TestCase):
    def test_jj_falls_back_to_plain_push_when_alias_absent(self):
        with (
            mock.patch.object(push, "detect_vcs", return_value=_jj_info("feat/1-x")),
            mock.patch.object(push.subprocess, "run", return_value=_alias_absent()),
        ):
            info = push.get_push_info("/repo")
        self.assertEqual(info["vcs"], "jj")
        self.assertEqual(info["method"], "confirm_and_push")
        self.assertEqual(info["push_command"], "jj git push --bookmark feat/1-x")
        self.assertEqual(info["branch"], "feat/1-x")
        self.assertFalse(info["safe_push_available"])

    def test_jj_without_bookmark_falls_back_to_plain_push(self):
        with (
            mock.patch.object(push, "detect_vcs", return_value=_jj_info(None)),
            mock.patch.object(push.subprocess, "run", return_value=_alias_absent()),
        ):
            info = push.get_push_info("/repo")
        self.assertEqual(info["method"], "confirm_and_push")
        self.assertEqual(info["push_command"], "jj git push")

    def test_jj_recommends_safe_push_when_alias_configured(self):
        with (
            mock.patch.object(push, "detect_vcs", return_value=_jj_info("feat/1-x")),
            mock.patch.object(push.subprocess, "run", return_value=_alias_present()),
        ):
            info = push.get_push_info("/repo")
        self.assertEqual(info["method"], "confirm_and_push")
        self.assertEqual(info["push_command"], "jj safe-push")
        self.assertTrue(info["safe_push_available"])

    def test_jj_no_longer_depends_on_safe_push_skill(self):
        with (
            mock.patch.object(push, "detect_vcs", return_value=_jj_info("b")),
            mock.patch.object(push.subprocess, "run", return_value=_alias_absent()),
        ):
            info = push.get_push_info("/repo")
        self.assertNotEqual(info["method"], "safe-push")
        self.assertNotIn("safe-push skill", info.get("instruction", ""))


class GetPushInfoGitTest(unittest.TestCase):
    def test_git_with_upstream_counts_unpushed(self):
        results = iter(
            [
                mock.Mock(returncode=0, stdout="origin/feat/2-y\n"),  # rev-parse @{u}
                mock.Mock(returncode=0, stdout="3\n"),  # rev-list --count
            ]
        )
        with (
            mock.patch.object(push, "detect_vcs", return_value=_git_info()),
            mock.patch.object(
                push.subprocess, "run", side_effect=lambda *a, **k: next(results)
            ),
        ):
            info = push.get_push_info("/repo")
        self.assertEqual(info["vcs"], "git")
        self.assertEqual(info["method"], "confirm_and_push")
        self.assertEqual(info["push_command"], "git push origin feat/2-y")
        self.assertTrue(info["has_upstream"])
        self.assertEqual(info["unpushed_commits"], 3)

    def test_git_without_upstream_uses_set_upstream(self):
        with (
            mock.patch.object(push, "detect_vcs", return_value=_git_info()),
            mock.patch.object(
                push.subprocess,
                "run",
                return_value=mock.Mock(returncode=1, stdout=""),
            ),
        ):
            info = push.get_push_info("/repo")
        self.assertEqual(info["push_command"], "git push -u origin feat/2-y")
        self.assertFalse(info["has_upstream"])
        self.assertEqual(info["unpushed_commits"], "all (new branch)")

    def test_git_without_branch_returns_error(self):
        with mock.patch.object(push, "detect_vcs", return_value=_git_info(None)):
            info = push.get_push_info("/repo")
        self.assertEqual(info["vcs"], "git")
        self.assertIn("error", info)


if __name__ == "__main__":
    unittest.main()
