#!/usr/bin/env python3
"""Push changes to remote. Outputs push command for Claude to execute."""

import json
import subprocess
import sys

from vcs import VCSType, detect_vcs


def _jj_safe_push_available(root_dir: str | None) -> bool:
    """Detect whether the optional `jj safe-push` alias is configured.

    The `jj safe-*` machinery lives in the external (optional) jj-exec-aliases
    tool, which registers a `aliases.safe-push` entry in jj config. We probe for
    it so the recommended command can adapt automatically instead of relying on
    the agent to switch manually. Returns False when jj is absent or the alias is
    not configured.
    """
    try:
        result = subprocess.run(
            ["jj", "config", "get", "aliases.safe-push"],
            capture_output=True,
            text=True,
            cwd=root_dir,
            check=False,
        )
    except OSError:
        return False
    return result.returncode == 0 and bool(result.stdout.strip())


def get_push_info(project_dir: str | None = None) -> dict:
    """Get information needed for pushing, without actually pushing.

    Returns the recommended push command and context for Claude
    to execute (with user confirmation, for both git and jj).
    """
    vcs_info = detect_vcs(project_dir)

    if vcs_info.vcs_type == VCSType.JJ:
        # For jj, provide the push command for user confirmation.
        # The jj-safe-* alias machinery lives in the external (optional)
        # jj-exec-aliases tool. If its `safe-push` alias is configured, recommend
        # it (it handles bookmark selection + divergence guard); otherwise fall
        # back to a plain `jj git push`.
        branch = vcs_info.current_branch
        if _jj_safe_push_available(vcs_info.root_dir):
            return {
                "vcs": "jj",
                "method": "confirm_and_push",
                "push_command": "jj safe-push",
                "instruction": (
                    "Confirm with the user, then push via the jj-exec-aliases "
                    "`jj safe-push` alias."
                ),
                "branch": branch,
                "safe_push_available": True,
                "remote_url": vcs_info.remote_url,
            }
        push_cmd = f"jj git push --bookmark {branch}" if branch else "jj git push"
        return {
            "vcs": "jj",
            "method": "confirm_and_push",
            "push_command": push_cmd,
            "instruction": (
                "Confirm with the user, then push. "
                "Install jj-exec-aliases to enable `jj safe-push`."
            ),
            "branch": branch,
            "safe_push_available": False,
            "remote_url": vcs_info.remote_url,
        }
    else:
        # For git, provide the push command for user confirmation
        branch = vcs_info.current_branch
        if not branch:
            return {
                "vcs": "git",
                "error": "Not on a branch. Cannot determine push target.",
            }

        # Check if branch has upstream
        upstream_ref = f"{branch}@{{u}}"
        result = subprocess.run(  # noqa: S603
            ["git", "rev-parse", "--abbrev-ref", upstream_ref],
            capture_output=True,
            text=True,
            cwd=vcs_info.root_dir,
            check=False,
        )

        has_upstream = result.returncode == 0

        # Count unpushed commits
        if has_upstream:
            rev_range = f"origin/{branch}..HEAD"
            count_result = subprocess.run(  # noqa: S603
                ["git", "rev-list", "--count", rev_range],
                capture_output=True,
                text=True,
                cwd=vcs_info.root_dir,
                check=False,
            )
            if count_result.returncode == 0:
                unpushed = int(count_result.stdout.strip())
            else:
                unpushed = "unknown"
        else:
            unpushed = "all (new branch)"

        push_cmd = f"git push origin {branch}"
        if not has_upstream:
            push_cmd = f"git push -u origin {branch}"

        return {
            "vcs": "git",
            "method": "confirm_and_push",
            "push_command": push_cmd,
            "branch": branch,
            "has_upstream": has_upstream,
            "unpushed_commits": unpushed,
            "remote_url": vcs_info.remote_url,
        }


def main():
    project_dir = sys.argv[1] if len(sys.argv) > 1 else None
    info = get_push_info(project_dir)
    print(json.dumps(info, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
