"""環境変数とパス解決。

VAULT_DIR / INDEX_DIR / モデル名を環境変数から解決する。marketplace 経由で
他環境に配布されても動くよう、明示 env を最優先にしつつ妥当なフォールバックを持つ。
"""

from __future__ import annotations

import os
from pathlib import Path

# デフォルトの埋め込みモデル。日本語実績が豊富で軽量・CPU で実用速度。
DEFAULT_MODEL = "intfloat/multilingual-e5-small"

# 走査から除外するディレクトリ名（どの階層でも一致したらスキップ）。
# ドット始まりは別途一律除外するため、ここには非ドットのものだけ列挙する。
EXCLUDE_DIRS: frozenset[str] = frozenset(
    {
        "node_modules",
        "dist",
        "plugins",  # プラグイン実装そのものは知識ではない
        "skills",  # SKILL.md（プラグイン内部定義）
        "hooks",  # フックスクリプト
        "meta",  # Obsidian ワークスペース設定
        "brain",  # CLAUDE.md により触れない領域
    }
)

# 走査対象の拡張子。
MARKDOWN_SUFFIXES: frozenset[str] = frozenset({".md", ".markdown"})


def _looks_like_vault(path: Path) -> bool:
    """ディレクトリが Vault らしいか判定する（.obsidian か、トップレベルに .md がある）。

    `rglob` ではなくトップレベルのみの `glob("*.md")` を使う。再帰走査しないため、
    誤って巨大ディレクトリ（ホームフォルダ等）を指定しても高 I/O にならない。
    """
    if (path / ".obsidian").is_dir():
        return True
    return next(path.glob("*.md"), None) is not None


def resolve_vault_dir() -> Path:
    """検索対象 Vault のルートを解決する。

    優先順:
      1. OBSIDIAN_SEMANTIC_VAULT_DIR（実在するディレクトリなら無条件に採用＝明示的な上書き）
      2. OBSIDIAN_VAULT_PATH（借用設定。Vault らしさを確認できた場合のみ採用）
      3. CLAUDE_PLUGIN_ROOT から上方向に `.obsidian/` を探索しその親
      4. カレントディレクトリ

    実在しない／空のパスは無視してフォールバックする。別マシンの Obsidian パスが
    env に残っていても、checkout 場所の Vault を正しく見つける（存在しない・空の
    パスを黙ってインデックスして 0 件になる事故を防ぐ）。
    """
    # 我々専用の明示上書き: 実在すれば無条件に信頼する。
    explicit = os.environ.get("OBSIDIAN_SEMANTIC_VAULT_DIR")
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if path.is_dir():
            return path

    # 借用設定（既存プラグインの env）: Vault らしさ（.obsidian か .md の存在）を確認。
    borrowed = os.environ.get("OBSIDIAN_VAULT_PATH")
    if borrowed:
        path = Path(borrowed).expanduser().resolve()
        if path.is_dir() and _looks_like_vault(path):
            return path

    start = os.environ.get("CLAUDE_PLUGIN_ROOT")
    base = Path(start).resolve() if start else Path.cwd().resolve()
    for candidate in (base, *base.parents):
        if (candidate / ".obsidian").is_dir():
            return candidate

    return Path.cwd().resolve()


def resolve_index_dir(vault_dir: Path) -> Path:
    """インデックスの保存先を解決する。

    OBSIDIAN_SEMANTIC_INDEX_DIR があればそれを、無ければ
    `<vault>/.obsidian-semantic-index/` を使う（gitignore 対象）。
    """
    explicit = os.environ.get("OBSIDIAN_SEMANTIC_INDEX_DIR")
    if explicit:
        return Path(explicit).expanduser().resolve()
    return vault_dir / ".obsidian-semantic-index"


def get_model_name() -> str:
    """埋め込みモデル名を返す（OBSIDIAN_SEMANTIC_MODEL で上書き可能）。"""
    return os.environ.get("OBSIDIAN_SEMANTIC_MODEL", DEFAULT_MODEL)


def is_excluded(rel_path: Path) -> bool:
    """相対パスが除外対象ディレクトリ配下、またはドット始まり要素を含むか。"""
    for part in rel_path.parts:
        if part.startswith("."):
            return True
        if part in EXCLUDE_DIRS:
            return True
    return False
