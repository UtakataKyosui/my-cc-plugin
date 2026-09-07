#!/usr/bin/env python3
"""Build triage input JSON for the pr-triage SubAgent.

Reads fetch_unanswered.py output and enriches each thread with:
- file_snippet (already present from fetch_unanswered)
- thread_diff_context: cleaned diff_hunk
- latest_comment_body: convenience field for the last comment text
"""

import json
import sys


def build_thread_diff_context(diff_hunk: str | None) -> str:
    """Format diff_hunk for readability."""
    if not diff_hunk:
        return ""
    lines = diff_hunk.splitlines()
    # Keep at most 30 lines to avoid overwhelming the agent
    if len(lines) > 30:
        lines = [*lines[:30], "... (truncated)"]
    return "\n".join(lines)


def enrich_thread(thread: dict) -> dict:
    """Add convenience fields to a thread dict."""
    comments = thread.get("comments", [])
    last_comment = comments[-1] if comments else {}
    root_comment = comments[0] if comments else {}

    return {
        **thread,
        "root_comment_id": root_comment.get("id"),
        "latest_comment_body": last_comment.get("body", ""),
        "latest_comment_author": last_comment.get("author", ""),
        "thread_diff_context": build_thread_diff_context(root_comment.get("diff_hunk")),
    }


def main():
    raw = sys.stdin.read()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON input: {e}"}))
        sys.exit(1)

    unanswered = data.get("unanswered_threads", [])
    if not unanswered:
        output = {
            "pr": data.get("pr", {}),
            "threads": [],
            "message": "未返信スレッドなし — triage 不要",
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
        sys.exit(0)

    enriched = [enrich_thread(t) for t in unanswered]

    output = {
        "pr": data.get("pr", {}),
        "threads": enriched,
        "thread_count": len(enriched),
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
