# インストール手順

## 前提条件

| ツール | バージョン | 用途 |
|---|---|---|
| [jj (Jujutsu)](https://jj-vcs.dev/latest/install/) | 0.37.0+ | VCS |
| [Lefthook](https://github.com/evilmartians/lefthook) | 2.1.0+ | Git Hook 管理 |
| [jq](https://jqlang.github.io/jq/) | 1.6+ | JSON パース |
| [jj-exec-aliases](https://github.com/UtakataKyosui/jj-exec-aliases) | - | `jj safe-new` / `jj safe-push` の提供（任意） |

## `/jj-init` コマンドで一括セットアップ（推奨）

```bash
/jj-init             # 基本セットアップ（rules 配置・Lefthook 設定）
/jj-init --lefthook  # Lefthook テンプレートも配置
```

以下の手動手順をすべて自動で行う。

---

## 手動セットアップ

### Step 1: jj safe-* コマンドの導入（jj-exec-aliases）

`jj safe-new` / `jj safe-push` は外部ツール
[jj-exec-aliases](https://github.com/UtakataKyosui/jj-exec-aliases) が提供する。
同リポジトリの手順に従って導入すると、jj alias として `jj safe-new` / `jj safe-push`
が登録され、スコープチェック＋ Lefthook 品質チェックを経由するようになる。

> このプラグインは以前 `scripts/jj-safe-*.sh` ＋ `install-jj-aliases.sh` を同梱していたが、
> jj は個人ツールであり、安全網一式（スクリプト・alias・ブロック hook・permissions・シェルラッパー）は
> jj-exec-aliases に集約した（Issue #19）。このプラグインは jj safe-* の実体を持たない。

### Step 2: rules ファイルの配置

`/jj-init` コマンドで自動配置するか、手動でコピーする:

```bash
mkdir -p .claude/rules
cp "${CLAUDE_PLUGIN_ROOT}/templates/jj-change-driven.md" .claude/rules/
cp "${CLAUDE_PLUGIN_ROOT}/templates/jj-troubleshooting-feedback.md" .claude/rules/
```

`CLAUDE.md` から参照する:

```markdown
<!-- CLAUDE.md -->
@.claude/rules/jj-change-driven.md
@.claude/rules/jj-troubleshooting-feedback.md
```

### Step 3: Lefthook の設定

テンプレートを参考に `lefthook.yml` を作成して `lefthook install` を実行する。

```bash
cp "${CLAUDE_PLUGIN_ROOT}/templates/lefthook.yml" lefthook.yml
# 内容をプロジェクトに合わせて編集
lefthook install
```

**重要**: `jj` にはステージングエリアがないため `{staged_files}` は使えない。
代わりに `jj diff --name-only` を `files:` に指定する。

### Step 4: シェルラッパーのインストール（任意）

ターミナルでの直接操作（`jj new` / `jj git push`）も `jj safe-*` へリダイレクトしたい場合は、
[jj-exec-aliases](https://github.com/UtakataKyosui/jj-exec-aliases) が提供するシェルラッパーを導入する。

### Step 5: 設定の確認

```bash
jj config list --repo | grep -E "(fix|aliases)"
```

## 動作確認

```bash
# jj safe-new が動くか（jj-exec-aliases 導入時）
jj describe -m "test: 動作確認"
jj safe-new -m "test: 次のChange"

# jj safe-push --dry-run が動くか
jj safe-push --dry-run
```

## アンインストール

`jj safe-*` の alias / シェルラッパーは
[jj-exec-aliases](https://github.com/UtakataKyosui/jj-exec-aliases) 側の手順に従って削除する。
