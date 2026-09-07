#!/usr/bin/env python3
"""Common helpers for pr-review-toolkit scripts."""

import json
import re
import subprocess
import sys


def parse_pr_reference(pr_ref: str) -> tuple[str | None, str]:
    """Parse PR reference into (repo, pr_number).

    Accepts:
      - Full URL: https://github.com/owner/repo/pull/123
      - Short reference: owner/repo#123
      - Just a number: 123
    """
    url_match = re.match(r"https?://github\.com/([^/]+/[^/]+)/pull/(\d+)", pr_ref)
    if url_match:
        return url_match.group(1), url_match.group(2)

    short_match = re.match(r"([^/]+/[^#]+)#(\d+)", pr_ref)
    if short_match:
        return short_match.group(1), short_match.group(2)

    if pr_ref.strip().isdigit():
        return None, pr_ref.strip()

    print(
        json.dumps({"error": f"Cannot parse PR reference: {pr_ref}"}), file=sys.stderr
    )
    sys.exit(1)


def detect_repo() -> str | None:
    """Detect repo name from current directory via gh CLI."""
    try:
        result = subprocess.run(
            ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        return None
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def run_gh(args: list[str], *, check: bool = True) -> subprocess.CompletedProcess:
    """Run a gh CLI command and return the result."""
    try:
        result = subprocess.run(  # noqa: S603
            ["gh", *args],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        print(
            json.dumps(
                {
                    "error": "GitHub CLI (gh) not found. Install from https://cli.github.com/"
                }
            ),
            file=sys.stderr,
        )
        sys.exit(1)
    if check and result.returncode != 0:
        msg = result.stderr.strip() or f"gh command failed: gh {' '.join(args)}"
        print(json.dumps({"error": msg}), file=sys.stderr)
        sys.exit(result.returncode)
    return result


def resolve_repo(repo: str | None) -> str:
    """Resolve repo, auto-detecting from cwd if None."""
    if repo:
        return repo
    detected = detect_repo()
    if not detected:
        print(
            json.dumps(
                {
                    "error": "Cannot detect repository. "
                    "Specify full PR URL or owner/repo#N."
                }
            ),
            file=sys.stderr,
        )
        sys.exit(1)
    return detected
