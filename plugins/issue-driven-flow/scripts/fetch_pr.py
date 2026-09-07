#!/usr/bin/env python3
"""Fetch PR metadata, diff, and file list in one structured JSON output.

Usage:
  fetch_pr.py <PR_REF> [--include-comments] [--no-diff]

PR_REF accepts:
  - Full URL: https://github.com/owner/repo/pull/123
  - Short:    owner/repo#123
  - Number:   123  (repo auto-detected from cwd)
"""

import argparse
import json

from pr_common import parse_pr_reference, resolve_repo, run_gh


def fetch_pr_meta(repo: str, pr_number: str) -> dict:
    result = run_gh(
        [
            "pr",
            "view",
            pr_number,
            "--repo",
            repo,
            "--json",
            "number,title,body,state,headRefName,baseRefName,author,url,"
            "additions,deletions,changedFiles,labels,reviewDecision,isDraft,"
            "createdAt,updatedAt,mergedAt",
        ]
    )
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        raise SystemExit("Error: Failed to parse PR metadata as JSON") from None


def fetch_pr_diff(repo: str, pr_number: str) -> str:
    result = run_gh(["pr", "diff", pr_number, "--repo", repo], check=False)
    if result.returncode != 0:
        return ""
    return result.stdout


def fetch_pr_files(repo: str, pr_number: str) -> list[dict]:
    result = run_gh(
        [
            "api",
            f"repos/{repo}/pulls/{pr_number}/files",
            "--paginate",
            "--slurp",
        ]
    )
    try:
        pages = json.loads(result.stdout)
        raw = [item for page in pages for item in page]
    except (json.JSONDecodeError, TypeError):
        return []
    return [
        {
            "path": f.get("filename", ""),
            "status": f.get("status", ""),  # added/removed/modified/renamed
            "additions": f.get("additions", 0),
            "deletions": f.get("deletions", 0),
            "changes": f.get("changes", 0),
            "previous_path": f.get("previous_filename"),
        }
        for f in raw
    ]


def fetch_pr_comments(repo: str, pr_number: str) -> list[dict]:
    result = run_gh(
        [
            "api",
            f"repos/{repo}/pulls/{pr_number}/comments",
            "--paginate",
            "--slurp",
        ]
    )
    try:
        pages = json.loads(result.stdout)
        raw = [item for page in pages for item in page]
    except (json.JSONDecodeError, TypeError):
        return []
    return [
        {
            "id": c.get("id"),
            "author": c.get("user", {}).get("login", "unknown"),
            "body": c.get("body", ""),
            "path": c.get("path"),
            "line": c.get("original_line") or c.get("line"),
            "diff_hunk": c.get("diff_hunk"),
            "in_reply_to_id": c.get("in_reply_to_id"),
            "created_at": c.get("created_at", ""),
        }
        for c in raw
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch PR contents as structured JSON")
    parser.add_argument("pr_ref", help="PR URL, owner/repo#N, or bare number")
    parser.add_argument(
        "--include-comments", action="store_true", help="Include inline review comments"
    )
    parser.add_argument(
        "--no-diff", action="store_true", help="Skip fetching unified diff"
    )
    args = parser.parse_args()

    repo_hint, pr_number = parse_pr_reference(args.pr_ref)
    repo = resolve_repo(repo_hint)

    meta = fetch_pr_meta(repo, pr_number)
    files = fetch_pr_files(repo, pr_number)
    diff = "" if args.no_diff else fetch_pr_diff(repo, pr_number)

    output: dict = {
        "pr": {
            "number": meta.get("number"),
            "title": meta.get("title"),
            "body": meta.get("body", ""),
            "state": meta.get("state"),
            "is_draft": meta.get("isDraft", False),
            "url": meta.get("url"),
            "head_branch": meta.get("headRefName"),
            "base_branch": meta.get("baseRefName"),
            "author": meta.get("author", {}).get("login"),
            "review_decision": meta.get("reviewDecision"),
            "labels": [lb.get("name") for lb in meta.get("labels", [])],
            "additions": meta.get("additions", 0),
            "deletions": meta.get("deletions", 0),
            "changed_files": meta.get("changedFiles", 0),
            "created_at": meta.get("createdAt"),
            "updated_at": meta.get("updatedAt"),
            "merged_at": meta.get("mergedAt"),
        },
        "files": files,
        "diff": diff,
    }

    if args.include_comments:
        output["comments"] = fetch_pr_comments(repo, pr_number)

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
