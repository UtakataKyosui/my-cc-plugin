#!/usr/bin/env python3
"""Analyze PR contents from fetch_pr.py output.

Usage:
  fetch_pr.py <PR_REF> | analyze_pr.py
  analyze_pr.py --from-fetch <path>
"""

import argparse
import json
import re
import sys

# Extension → language label
EXT_TO_LANG: dict[str, str] = {
    "py": "Python",
    "pyi": "Python",
    "ts": "TypeScript",
    "tsx": "TypeScript",
    "js": "JavaScript",
    "jsx": "JavaScript",
    "mjs": "JavaScript",
    "cjs": "JavaScript",
    "rs": "Rust",
    "go": "Go",
    "rb": "Ruby",
    "java": "Java",
    "kt": "Kotlin",
    "kts": "Kotlin",
    "swift": "Swift",
    "c": "C",
    "h": "C",
    "cpp": "C++",
    "cc": "C++",
    "cxx": "C++",
    "hpp": "C++",
    "cs": "C#",
    "sh": "Shell",
    "bash": "Shell",
    "zsh": "Shell",
    "md": "Markdown",
    "mdx": "Markdown",
    "json": "JSON",
    "jsonc": "JSON",
    "yaml": "YAML",
    "yml": "YAML",
    "toml": "TOML",
    "sql": "SQL",
    "html": "HTML",
    "css": "CSS",
    "scss": "CSS",
    "sass": "CSS",
    "tf": "Terraform",
    "tfvars": "Terraform",
    "dockerfile": "Docker",
}

# Test file patterns
TEST_PATTERNS = [
    re.compile(r"test[s]?/", re.IGNORECASE),
    re.compile(r"spec[s]?/", re.IGNORECASE),
    re.compile(r"__tests__/"),
    re.compile(r"\.(test|spec)\.[a-z]+$", re.IGNORECASE),
    re.compile(r"_test\.[a-z]+$", re.IGNORECASE),
]

# Package manifest files
MANIFEST_FILES = {
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Cargo.toml",
    "Cargo.lock",
    "go.mod",
    "go.sum",
    "requirements.txt",
    "pyproject.toml",
    "uv.lock",
    "poetry.lock",
    "Gemfile",
    "Gemfile.lock",
    "build.gradle",
    "pom.xml",
    "composer.json",
    "composer.lock",
}

# Sensitive file/content patterns
SECRET_PATTERNS = [
    (
        re.compile(
            r"(?i)(api[_-]?key|api[_-]?secret|access[_-]?token|private[_-]?key|secret[_-]?key)\s*[:=]\s*[\"']?[A-Za-z0-9+/\-_]{16,}"
        ),
        "credential_pattern",
    ),
    (re.compile(r"(?i)password\s*[:=]\s*[\"'][^\"']{4,}"), "password_literal"),
    (re.compile(r"(?i)-----BEGIN (RSA |EC |OPENSSH |)PRIVATE KEY-----"), "private_key"),
    (
        re.compile(r"(?i)(AKIA|ASIA|AROA|AIDA|AIPA|ANPA|ANVA|APKA)[A-Z0-9]{16}"),
        "aws_access_key",
    ),
    (re.compile(r"ghp_[A-Za-z0-9]{36}|github_pat_[A-Za-z0-9_]{82}"), "github_token"),
]

SENSITIVE_FILENAMES = re.compile(
    r"(?i)(\.env($|\.|\.local)|credentials?\.json|secrets?\.(yaml|yml|json|toml)|id_rsa|id_ed25519)"
)


def _is_test_file(path: str) -> bool:
    return any(p.search(path) for p in TEST_PATTERNS)


def _ext(path: str) -> str:
    dot = path.rfind(".")
    if dot == -1:
        return path.split("/")[-1].lower()
    return path[dot + 1 :].lower()


def analyze(data: dict) -> dict:
    files: list[dict] = data.get("files", [])
    diff_text: str = data.get("diff", "")
    pr = data.get("pr", {})

    # --- Summary ---
    total_add = pr.get("additions", 0) or sum(f.get("additions", 0) for f in files)
    total_del = pr.get("deletions", 0) or sum(f.get("deletions", 0) for f in files)
    changed = len(files)

    # --- By language ---
    by_lang: dict[str, dict] = {}
    test_files = []
    non_test_files = []
    manifest_changes = []
    large_files = []

    for f in files:
        path = f.get("path", "")
        adds = f.get("additions", 0)
        dels = f.get("deletions", 0)
        status = f.get("status", "")

        ext = _ext(path)
        lang = EXT_TO_LANG.get(ext, ext or "unknown")
        entry = by_lang.setdefault(lang, {"additions": 0, "deletions": 0, "files": 0})
        entry["additions"] += adds
        entry["deletions"] += dels
        entry["files"] += 1

        if _is_test_file(path):
            test_files.append(path)
        else:
            non_test_files.append(path)

        # Manifest check
        fname = path.split("/")[-1]
        if fname in MANIFEST_FILES:
            manifest_changes.append({"file": path, "status": status})

        # Large file check (>200 net changes)
        if adds + dels > 200:
            large_files.append({"path": path, "additions": adds, "deletions": dels})

    test_ratio = len(test_files) / changed if changed else 0.0

    # --- Security warnings ---
    warnings = []

    # Check for sensitive filenames in changed files
    for f in files:
        path = f.get("path", "")
        if SENSITIVE_FILENAMES.search(path):
            warnings.append(
                {
                    "type": "sensitive_filename",
                    "file": path,
                    "severity": "high",
                }
            )

    # Scan diff content for secret patterns
    if diff_text:
        current_file = "unknown"
        for line_no, line in enumerate(diff_text.splitlines(), 1):
            if line.startswith("+++ b/"):
                current_file = line[6:]
                continue
            if not line.startswith("+") or line.startswith("+++ "):
                continue
            content = line[1:]
            for pattern, kind in SECRET_PATTERNS:
                if pattern.search(content):
                    warnings.append(
                        {
                            "type": kind,
                            "file": current_file,
                            "diff_line": line_no,
                            "severity": "high",
                            "snippet": content.strip()[:120],
                        }
                    )

    return {
        "summary": {
            "total_additions": total_add,
            "total_deletions": total_del,
            "files_changed": changed,
            "test_files": len(test_files),
            "non_test_files": len(non_test_files),
        },
        "test_ratio": round(test_ratio, 3),
        "by_language": by_lang,
        "large_files": large_files,
        "manifest_changes": manifest_changes,
        "warnings": warnings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Analyze PR content from fetch_pr.py output"
    )
    parser.add_argument(
        "--from-fetch", help="Path to fetch_pr.py JSON output file (default: stdin)"
    )
    args = parser.parse_args()

    if args.from_fetch:
        with open(args.from_fetch) as f:
            data = json.load(f)
    else:
        raw = sys.stdin.read()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            print(json.dumps({"error": f"Invalid JSON input: {e}"}), file=sys.stderr)
            sys.exit(1)

    result = analyze(data)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
