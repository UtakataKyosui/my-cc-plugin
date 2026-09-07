#!/usr/bin/env python3
"""Fetch unanswered PR review threads via gh CLI + GraphQL.

An "unanswered" thread is one where the last comment was NOT posted by:
- The PR author (they replied, so it's answered)
- A bot account (github-actions[bot], dependabot[bot], etc.)
- The current authenticated user acting as responder

Uses REST API for comment data and GraphQL to get isResolved status.
"""

import json
import subprocess
import sys
from dataclasses import asdict

from review_fetcher import (
    ReviewThread,
    _detect_repo,
    fetch_pr_info,
    fetch_review_comments,
    group_into_threads,
    parse_pr_reference,
)

BOT_SUFFIXES = ("[bot]", "-bot", "bot")


def _is_bot(login: str) -> bool:
    return any(login.lower().endswith(s) for s in BOT_SUFFIXES)


def _get_current_user() -> str:
    result = subprocess.run(
        ["gh", "api", "user", "-q", ".login"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode == 0:
        return result.stdout.strip()
    return ""


def fetch_resolved_thread_ids(repo: str, pr_number: str) -> set[int]:
    """Use GraphQL to get resolved review thread IDs."""
    if "/" not in repo:
        print(
            f"[fetch_unanswered] Invalid repo format: '{repo}'. Expected 'owner/repo'.",
            file=sys.stderr,
        )
        return set()
    owner, name = repo.split("/", 1)
    query = """
query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) {
    pullRequest(number: $number) {
      reviewThreads(first: 100) {
        nodes {
          isResolved
          comments(first: 1) {
            nodes { databaseId }
          }
        }
      }
    }
  }
}
"""
    variables = json.dumps({"owner": owner, "name": name, "number": int(pr_number)})
    result = subprocess.run(  # noqa: S603
        [
            "gh",
            "api",
            "graphql",
            "-f",
            f"query={query}",
            "-f",
            f"variables={variables}",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return set()

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        return set()

    resolved_ids: set[int] = set()
    try:
        nodes = data["data"]["repository"]["pullRequest"]["reviewThreads"]["nodes"]
        for node in nodes:
            if node.get("isResolved"):
                comments = node.get("comments", {}).get("nodes", [])
                if comments and comments[0].get("databaseId"):
                    resolved_ids.add(comments[0]["databaseId"])
    except (KeyError, TypeError):
        pass

    return resolved_ids


def _is_unanswered(
    thread: ReviewThread, pr_author: str, bot_names: set[str], current_user: str = ""
) -> bool:
    """Determine if a thread needs a response.

    A thread is answered if its last comment was by the PR author, a bot,
    or the current authenticated user (responder).
    """
    if not thread.comments:
        return False
    last = thread.comments[-1]
    author = last.author or ""
    if author == pr_author:
        return False
    if current_user and author == current_user:
        return False
    return not (_is_bot(author) or author in bot_names)


def build_file_snippet(
    path: str | None, line: int | None, context_lines: int = 20
) -> str:
    """Read file_snippet around the target line."""
    if not path or not line:
        return ""
    try:
        from pathlib import Path as _Path

        content = _Path(path).read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()
        start = max(0, line - context_lines - 1)
        end = min(len(lines), line + context_lines)
        snippet_lines = lines[start:end]
        return "\n".join(f"{start + i + 1}: {ln}" for i, ln in enumerate(snippet_lines))
    except OSError:
        return ""


def main():
    if len(sys.argv) < 2:
        print(json.dumps({"error": "Usage: fetch_unanswered.py <PR_URL_or_number>"}))
        sys.exit(1)

    pr_ref = sys.argv[1]
    repo_arg, pr_number = parse_pr_reference(pr_ref)

    repo = repo_arg or _detect_repo()
    if not repo:
        print(json.dumps({"error": "Cannot detect repository. Specify full PR URL."}))
        sys.exit(1)

    pr_info = fetch_pr_info(repo_arg, pr_number)
    pr_author = pr_info.get("author", {}).get("login", "")
    current_user = _get_current_user()

    inline_comments = fetch_review_comments(repo_arg, pr_number)
    threads = group_into_threads(inline_comments)

    resolved_ids = fetch_resolved_thread_ids(repo, pr_number)

    unanswered: list[dict] = []
    skipped_resolved = 0
    skipped_answered = 0

    for thread in threads:
        if thread.thread_id in resolved_ids:
            skipped_resolved += 1
            continue
        if not _is_unanswered(thread, pr_author, set(), current_user):
            skipped_answered += 1
            continue
        t_dict = {
            "thread_id": thread.thread_id,
            "path": thread.path,
            "line": thread.line,
            "comment_count": len(thread.comments),
            "comments": [asdict(c) for c in thread.comments],
            "file_snippet": build_file_snippet(thread.path, thread.line),
        }
        unanswered.append(t_dict)

    output = {
        "pr": {
            "number": pr_info.get("number"),
            "title": pr_info.get("title"),
            "state": pr_info.get("state"),
            "url": pr_info.get("url"),
            "head_branch": pr_info.get("headRefName"),
            "base_branch": pr_info.get("baseRefName"),
            "author": pr_author,
            "repo": repo,
        },
        "summary": {
            "total_threads": len(threads),
            "unanswered": len(unanswered),
            "skipped_resolved": skipped_resolved,
            "skipped_answered": skipped_answered,
        },
        "unanswered_threads": unanswered,
    }

    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
