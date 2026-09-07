#!/usr/bin/env python3
"""Parse unified diff from fetch_pr.py output into structured JSON.

Usage:
  fetch_pr.py <PR_REF> | parse_diff.py
  parse_diff.py --diff-file <path>        # read raw diff from file
  parse_diff.py --from-fetch <path>       # read fetch_pr.py JSON output from file
"""

import argparse
import json
import re
import sys


def parse_unified_diff(diff_text: str) -> list[dict]:
    """Parse unified diff text into a list of per-file diff objects."""
    files: list[dict] = []
    current_file: dict | None = None
    current_hunk: dict | None = None
    old_lineno = 0
    new_lineno = 0

    for raw_line in diff_text.splitlines():
        # diff --git a/foo b/foo
        if raw_line.startswith("diff --git "):
            if current_hunk and current_file is not None:
                current_file["hunks"].append(current_hunk)
            if current_file is not None:
                files.append(current_file)
            # Parse paths from diff --git header as fallback (needed for binary diffs
            # that lack --- +++ headers).
            git_match = re.match(r"^diff --git a/(.+) b/(.+)$", raw_line)
            current_file = {
                "path": git_match.group(2) if git_match else "",
                "old_path": git_match.group(1) if git_match else "",
                "is_new": False,
                "is_deleted": False,
                "is_binary": False,
                "is_rename": False,
                "hunks": [],
            }
            current_hunk = None
            continue

        if current_file is None:
            continue

        if raw_line.startswith("new file mode"):
            current_file["is_new"] = True
        elif raw_line.startswith("deleted file mode"):
            current_file["is_deleted"] = True
        elif raw_line.startswith("rename from "):
            current_file["is_rename"] = True
            current_file["old_path"] = raw_line[len("rename from ") :]
        elif raw_line.startswith("rename to "):
            current_file["path"] = raw_line[len("rename to ") :]
        elif raw_line.startswith("Binary files"):
            current_file["is_binary"] = True
        elif raw_line.startswith("--- "):
            old_path = raw_line[4:]
            if old_path.startswith("a/"):
                old_path = old_path[2:]
            if not current_file["old_path"]:
                current_file["old_path"] = old_path if old_path != "/dev/null" else ""
        elif raw_line.startswith("+++ "):
            new_path = raw_line[4:]
            if new_path.startswith("b/"):
                new_path = new_path[2:]
            if not current_file["path"]:
                current_file["path"] = new_path if new_path != "/dev/null" else ""
            if not current_file["old_path"]:
                current_file["old_path"] = current_file["path"]
        elif raw_line.startswith("@@ "):
            if current_hunk is not None:
                current_file["hunks"].append(current_hunk)
            # @@ -old_start,old_lines +new_start,new_lines @@ optional context
            hunk_match = re.match(
                r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)", raw_line
            )
            if hunk_match:
                old_start = int(hunk_match.group(1))
                old_lines = int(hunk_match.group(2) or 1)
                new_start = int(hunk_match.group(3))
                new_lines = int(hunk_match.group(4) or 1)
                header_ctx = hunk_match.group(5).strip()
                old_lineno = old_start
                new_lineno = new_start
                current_hunk = {
                    "old_start": old_start,
                    "old_lines": old_lines,
                    "new_start": new_start,
                    "new_lines": new_lines,
                    "header": f"@@ -{old_start},{old_lines} +{new_start},{new_lines} @@"
                    + (f" {header_ctx}" if header_ctx else ""),
                    "lines": [],
                }
        elif current_hunk is not None:
            if raw_line.startswith("+"):
                current_hunk["lines"].append(
                    {
                        "type": "add",
                        "content": raw_line[1:],
                        "new_no": new_lineno,
                    }
                )
                new_lineno += 1
            elif raw_line.startswith("-"):
                current_hunk["lines"].append(
                    {
                        "type": "del",
                        "content": raw_line[1:],
                        "old_no": old_lineno,
                    }
                )
                old_lineno += 1
            elif raw_line.startswith(" ") or raw_line == "":
                current_hunk["lines"].append(
                    {
                        "type": "context",
                        "content": raw_line[1:] if raw_line else "",
                        "old_no": old_lineno,
                        "new_no": new_lineno,
                    }
                )
                old_lineno += 1
                new_lineno += 1
            elif raw_line.startswith("\\"):
                # "\ No newline at end of file"
                pass

    if current_hunk is not None and current_file is not None:
        current_file["hunks"].append(current_hunk)
    if current_file is not None:
        files.append(current_file)

    return files


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Parse unified diff into structured JSON"
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--diff-file", help="Path to a raw unified diff file")
    group.add_argument("--from-fetch", help="Path to fetch_pr.py JSON output file")
    args = parser.parse_args()

    if args.diff_file:
        with open(args.diff_file) as f:
            diff_text = f.read()
    elif args.from_fetch:
        with open(args.from_fetch) as f:
            data = json.load(f)
        diff_text = data.get("diff", "")
    else:
        # Read from stdin (piped from fetch_pr.py)
        raw = sys.stdin.read()
        try:
            data = json.loads(raw)
            diff_text = data.get("diff", "")
        except json.JSONDecodeError:
            # Treat stdin as raw diff
            diff_text = raw

    files = parse_unified_diff(diff_text)
    print(json.dumps({"files": files}, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
