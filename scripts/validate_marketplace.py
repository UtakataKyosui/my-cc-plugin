#!/usr/bin/env python3
"""Validate marketplace manifests, versions, and plugin file references."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def frontmatter_keys(path: Path) -> set[str] | None:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    try:
        end = lines[1:].index("---") + 1
    except ValueError:
        return None
    return {line.split(":", 1)[0].strip() for line in lines[1:end] if ":" in line}


def is_entrypoint(path: Path) -> bool:
    """Return whether a Markdown file is loaded as a Skill, Command, or Agent."""
    parts = path.parts
    if path.name == "SKILL.md":
        return True
    if "commands" in parts and "references" not in parts:
        return True
    if "agents" in parts and "templates" not in parts and path.name != "CONVENTIONS.md":
        return True
    return False


def validate(root: Path, strict_frontmatter: bool = False) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    marketplace_path = root / ".claude-plugin/marketplace.json"
    marketplace = json.loads(marketplace_path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for entry in marketplace["plugins"]:
        name = entry["name"]
        if name in names:
            errors.append(f"duplicate plugin name: {name}")
        names.add(name)
        plugin_root = root / entry["source"]
        manifest_path = plugin_root / ".claude-plugin/plugin.json"
        if not manifest_path.is_file():
            errors.append(f"missing manifest: {manifest_path}")
            continue
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("name") != name:
            errors.append(f"name mismatch: {name} != {manifest.get('name')}")
        if manifest.get("version") != entry.get("version"):
            errors.append(f"version mismatch: {name}")
        for directory in ("commands", "skills", "agents"):
            for path in (plugin_root / directory).rglob("*.md") if (plugin_root / directory).is_dir() else []:
                if not is_entrypoint(path):
                    continue
                keys = frontmatter_keys(path)
                if keys is None:
                    message = f"missing frontmatter: {path.relative_to(root)}"
                    (errors if strict_frontmatter else warnings).append(message)
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    parser.add_argument("--strict-frontmatter", action="store_true")
    args = parser.parse_args()
    errors, warnings = validate(args.root, args.strict_frontmatter)
    for warning in warnings:
        print(f"WARNING {warning}")
    for error in errors:
        print(f"ERROR {error}")
    print(f"validated marketplace: {len(errors)} errors, {len(warnings)} warnings")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
