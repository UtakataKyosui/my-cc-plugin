#!/usr/bin/env python3
"""全スコープから Skill/Agent/Command の frontmatter を抽出して JSON で出力する。

スコープ:
  repo        C2Lab plugins/ 配下
  user-global ~/.claude/skills, agents, commands
  marketplace ~/.claude/plugins/ 配下（外部プラグイン）
  builtin     data/builtin-commands.json（静的 manifest）
"""

import argparse
import json
import re
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).parent.parent
REPO_PLUGINS = Path(__file__).parent.parent.parent.parent / "plugins"
USER_GLOBAL = Path.home() / ".claude"
MARKETPLACE_BASE = Path.home() / ".claude" / "plugins"
BUILTIN_MANIFEST = PLUGIN_ROOT / "data" / "builtin-commands.json"

# description を単語トークン化するための stopword リスト（最小限）
_STOPWORDS = {
    "a",
    "an",
    "and",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "the",
    "this",
    "to",
    "use",
    "when",
    "with",
    "する",
    "ため",
    "場合",
    "以下",
    "以上",
    "に",
    "を",
    "は",
    "が",
    "で",
    "の",
    "と",
    "も",
    "か",
    "な",
    "し",
    "て",
    "れ",
    "さ",
    "る",
    "た",
}

# category_hint の正規表現マップ（先頭一致優先）
_CATEGORY_MAP: list[tuple[str, str]] = [
    (r"review|pr|pull.?request|レビュー", "pr-review"),
    (r"jj|jujutsu|vcs|version.?control|safe.?push|safe.?new", "vcs"),
    (r"screenshot|スクリーンショット|capture|playwright", "screenshot"),
    (r"tdd|test|coverage|spec|テスト", "testing"),
    (
        r"pnpm|npm|yarn|bun|uv pip|cargo.?install|package.?manager|パッケージ",
        "package-manager",
    ),
    (r"loop|schedule|cron|interval|recurring|自動|automation", "automation"),
    (r"security|vulnerability|semgrep|cve|ghasec|セキュリティ", "security"),
    (r"init|initialize|scaffold|setup|claude\.md", "project-setup"),
    (r"lint|format|refactor|simplify|clean|品質", "code-quality"),
    (r"plugin|skill|hook|agent|command|mcp|プラグイン", "plugin-dev"),
    (r"config|setting|permission|keybinding|help|設定", "meta"),
    (r"rust|cargo", "rust"),
    (r"tauri", "tauri"),
    (r"wasm|webassembly", "wasm"),
    (r"obsidian", "obsidian"),
    (r"kanban|タスク|task.?board", "kanban"),
]


def _tokenize(text: str) -> set[str]:
    """description を小文字・記号除去してトークン化する。

    英数字はスペース/ハイフン/アンダースコア区切りで分割。
    日本語はスペース・句読点で分割（文字レベルの断片化を避ける）。
    """
    # 英数字トークン: ハイフン/アンダースコア/スペースで分割
    ascii_words = re.findall(r"[a-z][a-z0-9]*", text.lower())
    # 日本語トークン: 3 文字以上の連続した日本語文字列
    jp_words = re.findall(r"[ぁ-んァ-ン一-龯々]{3,}", text)
    tokens = set(ascii_words) | set(jp_words)
    return {w for w in tokens if w not in _STOPWORDS and len(w) > 1}


def _category_hint(name: str, description: str, plugin: str = "") -> str:
    # プラグイン名による強制オーバーライド（description の誤マッチを防ぐ）
    _PLUGIN_OVERRIDES: dict[str, str] = {
        "tauri-app-dev": "tauri",
        "tauri-plugin-dev": "tauri",
        "obs-plugin-dev": "plugin-dev",
        "rust-cli-alternatives": "rust",
        "rust": "rust",
        "wasm-optimizer": "wasm",
        "activitypub": "other",
        "zenn-review": "pr-review",
        "code-review": "pr-review",
        "pr-lifecycle": "pr-review",
        "auto-pr-responder": "pr-review",
        "jj-vcs-workflow": "vcs",
        "obsidian-knowledge": "obsidian",
        "obsidian-memory": "obsidian",
        "vibe-kanban": "kanban",
    }
    if plugin in _PLUGIN_OVERRIDES:
        return _PLUGIN_OVERRIDES[plugin]

    combined = f"{name} {description}".lower()
    for pattern, category in _CATEGORY_MAP:
        if re.search(pattern, combined):
            return category
    return "other"


def _extract_frontmatter(content: str) -> dict | None:
    """--- で囲まれた YAML フロントマターを抽出して dict にする.

    folded scalar (>) と literal scalar (|) の継続行を連結して処理する。
    """
    if not content.startswith("---"):
        return None
    end = content.find("---", 3)
    if end == -1:
        return None
    yaml_str = content[3:end].strip()
    result: dict[str, str] = {}
    current_key: str | None = None
    current_val_lines: list[str] = []

    def _flush() -> None:
        if current_key is not None:
            result[current_key] = " ".join(current_val_lines).strip()

    for line in yaml_str.splitlines():
        if not line or (not line[0].isspace() and line.startswith("#")):
            continue
        if line and not line[0].isspace():
            _flush()
            current_key = None
            current_val_lines = []
            if ":" not in line:
                continue
            key, _, value = line.partition(":")
            val = value.strip().strip("\"'")
            if val in (">", "|", "|-", ">-", ">+", "|+"):
                current_key = key.strip()
            else:
                result[key.strip()] = val
        elif current_key is not None and line.strip():
            current_val_lines.append(line.strip())

    _flush()
    return result if result else None


def _make_asset(
    *,
    kind: str,
    source: str,
    plugin: str,
    path: str,
    name: str,
    description: str,
    doc_url: str = "",
) -> dict:
    tokens = sorted(_tokenize(description))
    return {
        "id": f"{source}:{path}",
        "kind": kind,
        "source": source,
        "plugin": plugin,
        "path": path,
        "name": name,
        "description": description,
        "tokens": tokens,
        "category_hint": _category_hint(name, description, plugin),
        **({"doc_url": doc_url} if doc_url else {}),
    }


def _scan_directory(
    base: Path,
    source: str,
    plugin_name: str,
) -> list[dict]:
    """base 配下の SKILL.md / agents/*.md / commands/**/*.md を走査する."""
    assets = []

    for kind, glob_pat in [
        ("skill", "skills/**/SKILL.md"),
        ("agent", "agents/*.md"),
        ("command", "commands/**/*.md"),
    ]:
        for fpath in base.glob(glob_pat):
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            fm = _extract_frontmatter(content)
            if not fm:
                continue
            name = fm.get("name", "").strip()
            desc = fm.get("description", "").strip()
            if not name or not desc:
                continue
            assets.append(
                _make_asset(
                    kind=kind,
                    source=source,
                    plugin=plugin_name,
                    path=str(fpath),
                    name=name,
                    description=desc,
                )
            )
    return assets


def extract_repo(plugins_dir: Path) -> list[dict]:
    """C2Lab plugins/ 配下を走査する."""
    assets = []
    for plugin_dir in sorted(plugins_dir.iterdir()):
        if not plugin_dir.is_dir() or plugin_dir.name.startswith("."):
            continue
        assets.extend(_scan_directory(plugin_dir, "repo", plugin_dir.name))
    return assets


def extract_user_global(user_dir: Path) -> list[dict]:
    """~/.claude/ 配下を走査する."""
    assets = []
    for kind, glob_pat in [
        ("skill", "skills/**/SKILL.md"),
        ("agent", "agents/*.md"),
        ("command", "commands/**/*.md"),
    ]:
        for fpath in user_dir.glob(glob_pat):
            # ~/.claude/plugins/ 配下は marketplace スコープで処理
            if ".claude/plugins" in str(fpath):
                continue
            try:
                content = fpath.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            fm = _extract_frontmatter(content)
            if not fm:
                continue
            name = fm.get("name", "").strip()
            desc = fm.get("description", "").strip()
            if not name or not desc:
                continue
            assets.append(
                _make_asset(
                    kind=kind,
                    source="user-global",
                    plugin="~/.claude",
                    path=str(fpath),
                    name=name,
                    description=desc,
                )
            )
    return assets


def extract_marketplace(marketplace_base: Path) -> list[dict]:
    """~/.claude/plugins/ 配下の外部プラグインを走査する."""
    assets = []
    if not marketplace_base.exists():
        return assets

    manifest_paths = list(marketplace_base.glob("**/.claude-plugin/plugin.json"))

    for manifest_path in manifest_paths:
        plugin_root = manifest_path.parent.parent
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            plugin_name = manifest.get("name", plugin_root.name)
        except (OSError, json.JSONDecodeError):
            plugin_name = plugin_root.name

        # source は "marketplace" 固定。plugin 名は plugin フィールドで表現する
        assets.extend(_scan_directory(plugin_root, "marketplace", plugin_name))

    return assets


def extract_builtin(manifest_path: Path) -> list[dict]:
    """data/builtin-commands.json を読み込んで asset リストに変換する."""
    if not manifest_path.exists():
        print(
            f"[extract_assets] WARNING: builtin manifest not found: {manifest_path}",
            file=sys.stderr,
        )
        return []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        print(
            f"[extract_assets] WARNING: failed to read builtin manifest: {e}",
            file=sys.stderr,
        )
        return []

    # NOTE: min_version フィールドは存在するが claude --version との照合は行っていない。
    # 全コマンドをバージョン未確認として取り込む（過検出側に倒す設計）。
    print(
        "[extract_assets] NOTE: builtin コマンドの min_version フィルタは未評価。"
        "全コマンドを取り込みます。",
        file=sys.stderr,
    )
    assets = []
    for cmd in manifest.get("commands", []):
        name = cmd.get("name", "").strip()
        desc = cmd.get("description", "").strip()
        if not name or not desc:
            continue
        asset = _make_asset(
            kind=cmd.get("kind", "command"),
            source="builtin",
            plugin="claude-code-builtin",
            path=cmd.get("slash", f"/{name}"),
            name=name,
            description=desc,
            doc_url=cmd.get("doc_url", ""),
        )
        if cmd.get("min_version"):
            asset["min_version_unverified"] = cmd["min_version"]
        assets.append(asset)
    return assets


def main() -> None:
    parser = argparse.ArgumentParser(
        description="全スコープから Skill/Agent/Command の frontmatter を抽出して JSON で出力する"
    )
    parser.add_argument(
        "--scope",
        default="all",
        help="カンマ区切りで指定: repo,user-global,marketplace,builtin または all (デフォルト: all)",
    )
    parser.add_argument(
        "--plugins-dir",
        default=str(REPO_PLUGINS),
        help=f"C2Lab plugins/ ディレクトリのパス (デフォルト: {REPO_PLUGINS})",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="出力先ファイルパス。- で標準出力 (デフォルト: -)",
    )
    args = parser.parse_args()

    scopes = (
        {"repo", "user-global", "marketplace", "builtin"}
        if args.scope == "all"
        else {s.strip() for s in args.scope.split(",")}
    )

    assets: list[dict] = []

    if "repo" in scopes:
        plugins_dir = Path(args.plugins_dir)
        if plugins_dir.exists():
            assets.extend(extract_repo(plugins_dir))
        else:
            print(
                f"[extract_assets] WARNING: plugins dir not found: {plugins_dir}",
                file=sys.stderr,
            )

    if "user-global" in scopes:
        assets.extend(extract_user_global(USER_GLOBAL))

    if "marketplace" in scopes:
        assets.extend(extract_marketplace(MARKETPLACE_BASE))

    if "builtin" in scopes:
        assets.extend(extract_builtin(BUILTIN_MANIFEST))

    output_json = json.dumps(
        {"count": len(assets), "assets": assets},
        ensure_ascii=False,
        indent=2,
    )

    if args.output == "-":
        print(output_json)
    else:
        Path(args.output).write_text(output_json, encoding="utf-8")
        print(
            f"[extract_assets] {len(assets)} assets written to {args.output}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
