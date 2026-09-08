#!/usr/bin/env python3
"""Create a MyZenns article issue after explicit user confirmation.

This wrapper keeps the side effect in a small, testable program and refuses to
run unless the caller supplies --confirmed.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


def run_gh(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["gh", *args],
        check=False,
        capture_output=True,
        text=True,
    )


def existing_labels(repo: str) -> set[str]:
    result = run_gh("label", "list", "--repo", repo, "--limit", "100", "--json", "name")
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "gh label list failed")
    return {item["name"] for item in json.loads(result.stdout)}


def create_issue(repo: str, title: str, body_file: Path, labels: list[str]) -> str:
    result = run_gh(
        "issue",
        "create",
        "--repo",
        repo,
        "--title",
        title,
        *sum((["--label", label] for label in labels), []),
        "--body-file",
        str(body_file),
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "gh issue create failed")
    return result.stdout.strip()


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--body-file", type=Path, required=True)
    parser.add_argument("--label", action="append", default=["zenn", "article"])
    parser.add_argument("--confirmed", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    if not args.confirmed:
        print("refusing to create an issue without --confirmed", file=sys.stderr)
        return 2
    if not args.body_file.is_file():
        print(f"body file does not exist: {args.body_file}", file=sys.stderr)
        return 2
    try:
        missing = set(args.label) - existing_labels(args.repo)
        if missing:
            print(f"missing labels in {args.repo}: {', '.join(sorted(missing))}", file=sys.stderr)
            return 2
        print(create_issue(args.repo, args.title, args.body_file, args.label))
    except (RuntimeError, json.JSONDecodeError) as error:
        print(str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
