#!/usr/bin/env python3
"""Validate Claude Code extension entrypoints without loading their prompts."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REQUIRED = {
    "skill": {"name", "description"},
    "subagent": {"name", "description"},
    "rule": set(),
}


def frontmatter(path: Path) -> tuple[dict[str, str], list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, ["YAML frontmatter is missing"]
    try:
        end = lines[1:].index("---") + 1
    except ValueError:
        return {}, ["YAML frontmatter is not closed"]
    values: dict[str, str] = {}
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$", line)
        if match:
            values[match.group(1)] = match.group(2).strip()
    return values, []


def infer_kind(path: Path) -> str:
    if path.name == "SKILL.md":
        return "skill"
    if "agents" in path.parts:
        return "subagent"
    return "rule"


def validate(path: Path, kind: str | None = None) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    if path.is_dir() and (path / "SKILL.md").is_file():
        path = path / "SKILL.md"
    manifest_path = path / ".claude-plugin/plugin.json" if path.is_dir() else None
    if manifest_path and manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as error:
            return [f"invalid plugin.json: {error}"], []
        for key in ("name", "version", "description"):
            if not manifest.get(key):
                errors.append(f"plugin.json is missing {key}")
        return errors, warnings
    if not path.is_file():
        return [f"target does not exist: {path}"], []
    selected = kind or infer_kind(path)
    values, parse_errors = frontmatter(path)
    errors.extend(parse_errors)
    for key in REQUIRED.get(selected, set()):
        if not values.get(key):
            errors.append(f"frontmatter is missing {key}")
    if selected == "skill" and values.get("name") and path.parent.name != values["name"]:
        errors.append("skill name must match its directory name")
    if selected == "subagent":
        for key in ("model", "tools", "maxTurns"):
            if key not in values:
                warnings.append(f"subagent frontmatter does not declare {key}")
        if "Bash" in values.get("tools", "") and "disallowedTools" not in values:
            warnings.append("reviewers with Bash should declare disallowedTools or explain the need")
    if selected == "rule" and "paths" not in values:
        warnings.append("rule has no paths scope; it will load globally")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", type=Path)
    parser.add_argument("--kind", choices=sorted(REQUIRED))
    args = parser.parse_args()
    errors, warnings = validate(args.target, args.kind)
    report = {
        "target": str(args.target),
        "errors": errors,
        "warnings": warnings,
        "status": "PASS" if not errors else "FAIL",
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
