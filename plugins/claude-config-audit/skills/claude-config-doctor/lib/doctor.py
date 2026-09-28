#!/usr/bin/env python3
"""~/.claude の Rules / Skills / Hooks / Agents / Plugins の整合性を機械的に検査する。

使い方: python3 doctor.py [--root ~/.claude] [--json]
終了コード: 問題が 1 件以上あれば 1、なければ 0。
"""
import argparse
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

FINDINGS = []


def add(kind, target, msg, owner="dotclaude"):
    FINDINGS.append({"kind": kind, "target": str(target), "msg": msg, "owner": owner})


def frontmatter(path):
    text = path.read_text(errors="replace")
    if not text.startswith("---"):
        return None, text
    parts = text.split("\n---", 1)
    if len(parts) < 2:
        return None, text
    fm = {}
    for line in parts[0].splitlines()[1:]:
        m = re.match(r"^([A-Za-z_-]+):\s*(.*)$", line)
        if m:
            fm[m.group(1)] = m.group(2).strip()
    return fm, parts[1]


def expand(cmd, home):
    return cmd.replace("$HOME", home).replace("~", home)


def check_hooks_config(hooks_cfg, root, home, owner, label):
    referenced = set()
    for event, groups in hooks_cfg.items():
        for g in groups:
            for h in g.get("hooks", []):
                if h.get("type") != "command":
                    continue
                raw = h.get("command", "")
                if re.search(r"/(Users|home)/[A-Za-z0-9._-]+/", raw):
                    add("hardcoded-home", f"{label}:{event}", f"絶対パス /Users/... がハードコードされている: {raw}", owner)
                cmd = raw.replace("${CLAUDE_PLUGIN_ROOT}", str(root)).replace("$CLAUDE_PLUGIN_ROOT", str(root))
                words = expand(cmd, home).split()
                script = None
                for w in words:
                    if w.startswith(("bash", "python3", "sh")) and "/" not in w:
                        continue
                    w = w.strip("'\"")
                    if "/" in w:
                        script = w
                        break
                if script is None:
                    continue
                p = Path(script)
                referenced.add(p.resolve())
                if not p.exists():
                    add("hook-missing", f"{label}:{event}", f"フックの実体が存在しない: {script}", owner)
                elif not os.access(p, os.X_OK) and not words[0].startswith(("bash", "python3", "sh")):
                    add("hook-not-executable", f"{label}:{event}", f"実行権限がない: {script}", owner)
                t = h.get("timeout")
                if t is not None and t > 600:
                    add("hook-timeout-unit", f"{label}:{event}", f"timeout={t} は秒単位として大きすぎる。ミリ秒と混同している可能性: {script}", owner)
    return referenced


def check_orphan_hooks(root, referenced):
    hooks_dir = root / "hooks"
    all_text = ""
    for sub in ("hooks", "skills", "rules", "agents", "commands"):
        d = root / sub
        if d.exists():
            for f in d.rglob("*"):
                if f.is_file() and f.suffix in (".sh", ".md", ".py", ".json", ".toml"):
                    try:
                        all_text += f.read_text(errors="replace")
                    except Exception:
                        pass
    settings_path = root / "settings.json"
    if settings_path.exists():
        all_text += settings_path.read_text()
    hooks_text = ""
    for f in hooks_dir.rglob("*"):
        if f.is_file() and f.suffix in (".sh", ".py"):
            hooks_text += f.read_text(errors="replace")
    for f in sorted(hooks_dir.iterdir()):
        if f.is_dir() or f.name.startswith("."):
            continue
        if f.resolve() in referenced:
            continue
        if f.name in hooks_text:
            continue  # 他のフックから呼ばれる補助ファイルは登録不要
        if f.name not in all_text:
            add("hook-orphan", f"hooks/{f.name}", "settings.json からも他ファイルからも参照されていない")
        else:
            add("hook-unregistered", f"hooks/{f.name}", "settings.json に登録されていない（rules や skills から言及のみ）")


REF_RE = re.compile(r"`((?:~/\.claude/|\$HOME/\.claude/)?(?:rules|skills|hooks|agents|commands)/[A-Za-z0-9_./-]+)`")


def check_refs(root):
    for sub in ("rules", "skills", "agents", "commands"):
        d = root / sub
        if not d.exists():
            continue
        for f in d.rglob("*.md"):
            if f.is_relative_to(root / "skills" / "synced"):
                continue  # claude.ai から同期されるバケット。中身は手元で管理しない
            text = f.read_text(errors="replace")
            for m in REF_RE.finditer(text):
                ref = m.group(1)
                line = text[text.rfind("\n", 0, m.start()) + 1 : text.find("\n", m.end())]
                if "プラグイン" in line or "plugin" in line.lower():
                    continue
                rel = re.sub(r"^(~|\$HOME)/\.claude/", "", ref).rstrip("/")
                p = root / rel
                if not p.exists() and not (root / rel).with_suffix("").exists():
                    add("broken-ref", str(f.relative_to(root)), f"参照先が存在しない: {ref}")


def check_rules(root):
    for f in sorted((root / "rules").glob("*.md")):
        fm, body = frontmatter(f)
        if fm and "paths" in fm:
            pass
        text = f.read_text(errors="replace")
        for word in ("gh my-task", "cmux", "jj-safe-push Skill", "junct-task-timer", "junct-estimate", "junct-task-lookup"):
            if word in text and "廃止" not in text and "削除済み" not in text and "移した" not in text and "junct-workflow:" not in text:
                add("stale-mention", f"rules/{f.name}", f"廃止・移行済みの名前に言及: {word}")


def check_skills(root):
    sk = root / "skills"
    if not sk.exists():
        return
    for d in sorted(sk.iterdir()):
        if d.is_symlink():
            add("skill-symlink", f"skills/{d.name}", f"シンボリックリンクで {os.readlink(d)} を指している。他マシンでは壊れる")
            continue
        if not d.is_dir() or d.name == "synced":
            continue
        if (d / ".claude-plugin" / "plugin.json").exists():
            # claude plugin init が置くプラグイン（<name>@skills-dir）。Skill ではない
            continue
        sk = d / "SKILL.md"
        if not sk.exists():
            add("skill-no-skillmd", f"skills/{d.name}", "SKILL.md がない")
            continue
        fm, _ = frontmatter(sk)
        if fm is None:
            add("skill-no-frontmatter", f"skills/{d.name}", "frontmatter がない")
            continue
        if fm.get("name") and fm["name"] != d.name:
            add("skill-name-mismatch", f"skills/{d.name}", f"name={fm['name']} がディレクトリ名と一致しない")
        if not fm.get("description"):
            add("skill-no-description", f"skills/{d.name}", "description が空。モデルが自動起動できない")
        user_only = fm.get("disable-model-invocation") == "true"
        for k in ("model", "effort"):
            if k in fm and not (k == "effort" and user_only):
                add("skill-model-effort", f"skills/{d.name}", f"frontmatter に {k} がある。インライン読込時にターン全体を汚染する")
        try:
            ignored = subprocess.run(["git", "check-ignore", "-q", str(d)], cwd=root, capture_output=True).returncode == 0
        except (OSError, subprocess.SubprocessError):
            ignored = False
        if ignored:
            add("skill-gitignored", f"skills/{d.name}", "ディレクトリ全体が gitignore されている。新しいマシンでは存在しない")
            continue
        for lib in d.rglob("*.sh"):
            if not os.access(lib, os.X_OK) and "lib" not in lib.parts:
                add("script-not-executable", str(lib.relative_to(root)), "実行権限がない")


def check_agents(root):
    for f in sorted((root / "agents").glob("*.md")):
        fm, _ = frontmatter(f)
        if fm is None:
            add("agent-no-frontmatter", f"agents/{f.name}", "frontmatter がない")
            continue
        if "model" not in fm:
            add("agent-no-model", f"agents/{f.name}", "model が未指定")
        if "disallowed-tools" in fm:
            add("agent-bad-key", f"agents/{f.name}", "disallowed-tools はケバブケースで無視される。disallowedTools にする")
        if fm.get("skills") is not None or "skills:" in f.read_text():
            pass


def check_plugins(root, home):
    settings = json.loads((root / "settings.json").read_text())
    enabled = {k for k, v in settings.get("enabledPlugins", {}).items() if v}
    inst_p = root / "plugins" / "installed_plugins.json"
    mk_p = root / "plugins" / "known_marketplaces.json"
    if not inst_p.exists() or not mk_p.exists():
        return  # clone 先など plugins/ がない場所ではプラグイン検査を飛ばす
    installed = json.loads(inst_p.read_text())["plugins"]
    markets = json.loads(mk_p.read_text())
    for key in sorted(enabled):
        name, market = key.split("@")
        src = markets.get(market, {}).get("source", {})
        repo = src.get("repo") or src.get("url", "")
        owner = repo if repo else market
        entries = [e for e in installed.get(key, []) if e["scope"] == "user"]
        if not entries:
            add("plugin-enabled-not-installed", key, "enabledPlugins にあるが user スコープでインストールされていない", owner)
            continue
        proot = Path(entries[0]["installPath"])
        if not proot.exists():
            add("plugin-cache-missing", key, f"キャッシュが存在しない: {proot}", owner)
            continue
        hj = proot / "hooks" / "hooks.json"
        if hj.exists():
            try:
                cfg = json.loads(hj.read_text())
                if "modules" in cfg and "hooks" not in cfg:
                    # 関数フックのプラグイン。modules は hooks.json からの相対パス
                    for mod in cfg["modules"]:
                        if not (hj.parent / mod).exists():
                            add("hook-missing", key, f"module が存在しない: {mod}", owner)
                else:
                    check_hooks_config(cfg.get("hooks", cfg), proot, home, owner, key)
            except Exception as e:
                add("plugin-hooks-json-invalid", key, f"hooks.json を読めない: {e}", owner)
        for sk in (proot / "skills").glob("*/SKILL.md") if (proot / "skills").exists() else []:
            fm, _ = frontmatter(sk)
            if fm is None or not fm.get("description"):
                add("plugin-skill-no-description", f"{key}:skills/{sk.parent.name}", "description が空", owner)
        for ag in (proot / "agents").rglob("*.md") if (proot / "agents").exists() else []:
            fm, _ = frontmatter(ag)
            if fm is None or "name" not in fm:
                add("plugin-agent-not-agent", f"{key}:{ag.relative_to(proot)}", "agents/ 配下に agent frontmatter のないファイルがある。エージェントとして誤登録される", owner)
        for cmd in (proot / "commands").rglob("*.md") if (proot / "commands").exists() else []:
            fm, _ = frontmatter(cmd)
            if fm is None or not fm.get("description"):
                add("plugin-command-no-description", f"{key}:{cmd.relative_to(proot)}", "description が空", owner)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=os.path.expanduser("~/.claude"))
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    root = Path(a.root)
    home = os.path.expanduser("~")
    settings = json.loads((root / "settings.json").read_text())
    referenced = check_hooks_config(settings.get("hooks", {}), root, home, "dotclaude", "settings.json")
    check_orphan_hooks(root, referenced)
    check_refs(root)
    check_rules(root)
    check_skills(root)
    check_agents(root)
    check_plugins(root, home)
    if a.json:
        print(json.dumps(FINDINGS, ensure_ascii=False, indent=1))
    else:
        for f in FINDINGS:
            print(f"[{f['owner']}] {f['kind']:28} {f['target']}: {f['msg']}")
        print(f"\n{len(FINDINGS)} findings", file=sys.stderr)
    sys.exit(1 if FINDINGS else 0)


if __name__ == "__main__":
    main()
