#!/usr/bin/env python3
"""Build a GitHub suggestion block from before/after file content at a given line.

Limitations:
- Only single-line suggestions are supported (multi-line returns empty string).
- The caller should fall back to needs-human if suggestion_block is empty.

GitHub suggestion syntax:
```suggestion
<replacement line(s)>
```
"""

import argparse
import difflib
import json
import sys
from pathlib import Path


def extract_new_line(before_path: str, after_path: str, line: int) -> str | None:
    """Extract the new content at `line` (1-based) from after_path.

    Uses difflib to track line shifts caused by insertions/deletions so that
    the before line number maps correctly to the corresponding after line.
    """
    try:
        before_lines = Path(before_path).read_text(encoding="utf-8").splitlines()
        after_lines = Path(after_path).read_text(encoding="utf-8").splitlines()
    except OSError as e:
        print(f"[build_suggestion] Cannot read file: {e}", file=sys.stderr)
        return None

    # Walk the diff opcodes to find what after-line corresponds to `line`
    matcher = difflib.SequenceMatcher(None, before_lines, after_lines, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            # before[i1:i2] == after[j1:j2]; check if `line` falls here
            if i1 < line <= i2:
                after_idx = j1 + (line - 1 - i1)
                before_line = before_lines[line - 1]
                after_line = after_lines[after_idx]
                if before_line == after_line:
                    return None  # unchanged
                return after_line
        elif tag in ("replace", "delete") and i1 < line <= i2:
            if tag == "delete":
                return None  # line was deleted
            # replaced: return the corresponding after line if it exists
            after_idx = j1 + (line - 1 - i1)
            if after_idx < j2:
                return after_lines[after_idx]
            return None

    return None


def build_suggestion_block(new_content: str) -> str:
    """Wrap new_content in a GitHub suggestion code fence."""
    return f"```suggestion\n{new_content}\n```"


def main():
    parser = argparse.ArgumentParser(description="Build GitHub suggestion block")
    parser.add_argument("--before", required=True, help="Path to original file")
    parser.add_argument("--after", required=True, help="Path to modified file")
    parser.add_argument(
        "--line", required=True, type=int, help="1-based line number to suggest"
    )
    args = parser.parse_args()

    new_content = extract_new_line(args.before, args.after, args.line)
    if new_content is None:
        result = {"suggestion_block": "", "reason": "no change at line or multi-line"}
    else:
        result = {"suggestion_block": build_suggestion_block(new_content)}

    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
