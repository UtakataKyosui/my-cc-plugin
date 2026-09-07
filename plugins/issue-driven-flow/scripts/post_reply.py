#!/usr/bin/env python3
"""Post inline threaded replies to GitHub PR review comments.

IMPORTANT: Always uses `gh api -X POST repos/.../pulls/.../comments` with
`in_reply_to` to post inside an existing thread. NEVER uses `gh pr comment`
(which posts a general/top-level PR comment, not a threaded reply).

Idempotency: successfully posted thread IDs are recorded in
/tmp/pr-replies-posted-<pr_number>.json to prevent duplicate replies on re-runs.
"""

import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path


def _posted_ids_path(pr_number: str | int, repo: str = "") -> Path:
    repo_slug = repo.replace("/", "_") if repo else ""
    prefix = f"{repo_slug}-" if repo_slug else ""
    return Path(tempfile.gettempdir()) / f"pr-replies-posted-{prefix}{pr_number}.json"


def _load_posted_ids(pr_number: str | int, repo: str = "") -> set[int]:
    path = _posted_ids_path(pr_number, repo)
    if not path.is_file():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return set(data.get("posted_thread_ids", []))
    except (json.JSONDecodeError, OSError):
        return set()


def _save_posted_ids(pr_number: str | int, ids: set[int], repo: str = "") -> None:
    path = _posted_ids_path(pr_number, repo)
    path.write_text(
        json.dumps({"posted_thread_ids": sorted(ids)}, indent=2),
        encoding="utf-8",
    )


def _detect_repo() -> str | None:
    result = subprocess.run(
        [
            "gh",
            "repo",
            "view",
            "--json",
            "nameWithOwner",
            "-q",
            ".nameWithOwner",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip()


def post_reply(
    repo: str,
    pr_number: str | int,
    root_comment_id: int,
    body: str,
    dry_run: bool = False,
) -> dict:
    """Post a single inline threaded reply.

    Uses `gh api -X POST` with in_reply_to — never `gh pr comment`.
    """
    url = f"repos/{repo}/pulls/{pr_number}/comments"
    cmd = [
        "gh",
        "api",
        "-X",
        "POST",
        url,
        "-f",
        f"body={body}",
        "-F",
        f"in_reply_to={root_comment_id}",
    ]

    if dry_run:
        return {
            "dry_run": True,
            "would_run": " ".join(cmd),
            "root_comment_id": root_comment_id,
            "body_preview": body[:200],
        }

    for attempt in range(2):
        result = subprocess.run(  # noqa: S603
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            try:
                resp = json.loads(result.stdout)
                return {
                    "success": True,
                    "comment_id": resp.get("id"),
                    "attempt": attempt + 1,
                }
            except json.JSONDecodeError:
                return {"success": True, "attempt": attempt + 1}

        if attempt == 0 and result.returncode == 1:
            # Retry only on likely rate-limit; skip permanent errors (404, 422 etc.)
            stderr_lower = result.stderr.lower()
            if any(
                kw in stderr_lower
                for kw in ("rate limit", "secondary rate", "abuse", "too many requests")
            ):
                time.sleep(2)
                continue

        print(
            f"[auto-pr-responder] post_reply FAILED (attempt {attempt + 1}): "
            f"{result.stderr.strip()}",
            file=sys.stderr,
        )
        return {
            "success": False,
            "error": result.stderr.strip(),
            "attempt": attempt + 1,
        }

    return {"success": False, "error": "max retries reached"}


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Post inline threaded replies to PR review threads"
    )
    parser.add_argument("--reply-file", required=True, help="Path to triage JSON")
    parser.add_argument("--repo", help="owner/repo (auto-detected if omitted)")
    parser.add_argument(
        "--pr-number", type=int, help="PR number (required when reply-file is a list)"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Print commands without posting"
    )
    args = parser.parse_args()

    repo = args.repo or _detect_repo()
    if not repo:
        print(json.dumps({"error": "Cannot detect repo. Use --repo owner/repo"}))
        sys.exit(1)

    reply_file = Path(args.reply_file)
    if not reply_file.is_file():
        print(json.dumps({"error": f"reply-file not found: {args.reply_file}"}))
        sys.exit(1)

    try:
        triage = json.loads(reply_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(json.dumps({"error": f"Invalid JSON: {e}"}))
        sys.exit(1)

    pr_number = args.pr_number
    # Try to extract PR number from triage file (pr-triage output has pr.number)
    if isinstance(triage, dict) and "pr" in triage:
        pr_number = pr_number or triage["pr"].get("number")
        threads = triage.get("results", [])
    elif isinstance(triage, list):
        threads = triage
    else:
        threads = []

    if pr_number is None:
        print(
            json.dumps(
                {
                    "error": "Cannot determine PR number."
                    " Use --pr-number when reply-file is a list"
                }
            )
        )
        sys.exit(1)

    pr_number_str = str(pr_number)
    posted_ids = _load_posted_ids(pr_number_str, repo)

    results = []
    any_failure = False

    for entry in threads:
        thread_id = entry.get("thread_id")
        if thread_id is None:
            continue

        # Skip invalid categories
        category = entry.get("category", "")
        if category == "needs-human":
            results.append(
                {"thread_id": thread_id, "skipped": True, "reason": "needs-human"}
            )
            continue

        # Idempotency: skip already-posted threads
        if thread_id in posted_ids:
            results.append(
                {"thread_id": thread_id, "skipped": True, "reason": "already posted"}
            )
            continue

        reply_draft = entry.get("reply_draft", "")
        suggestion_block = entry.get("suggestion_block", "")
        if suggestion_block:
            body = (
                f"{reply_draft}\n\n{suggestion_block}"
                if reply_draft
                else suggestion_block
            )
        else:
            body = reply_draft

        if not body:
            results.append(
                {"thread_id": thread_id, "skipped": True, "reason": "no reply_draft"}
            )
            continue

        root_comment_id = entry.get("root_comment_id") or thread_id
        result = post_reply(
            repo, pr_number_str, root_comment_id, body, dry_run=args.dry_run
        )
        result["thread_id"] = thread_id
        results.append(result)

        if not args.dry_run and result.get("success"):
            posted_ids.add(thread_id)
            _save_posted_ids(pr_number_str, posted_ids, repo)
        elif not args.dry_run and not result.get("success"):
            any_failure = True

    summary = {
        "repo": repo,
        "pr_number": pr_number,
        "dry_run": args.dry_run,
        "total": len(results),
        "posted": sum(1 for r in results if r.get("success")),
        "skipped": sum(1 for r in results if r.get("skipped")),
        "failed": sum(
            1
            for r in results
            if not r.get("success") and not r.get("skipped") and not r.get("dry_run")
        ),
        "results": results,
    }

    print(json.dumps(summary, indent=2, ensure_ascii=False))

    if any_failure:
        sys.exit(1)


if __name__ == "__main__":
    main()
