---
name: auto-pr-responder
description: >
  PR レビューコメントへの自律応答ワークフロー。以下の場合に使用:
  (1) /pr-workflow:respond で明示的に呼び出されたとき
  (2) 「PR の未返信コメントを処理」「レビューにまとめて返信」と指示されたとき
  (3) --dry-run で実行予定を確認したいとき
  (4) PR レビュー対応でスレッドへの inline threaded reply を投稿したいとき
  (5) general コメント誤投稿を防ぎたいとき
  手動で各スレッドを確認しながら対応したい場合は /pr-workflow:respond-manual を使う。
---

# auto-pr-responder

PR レビューの未返信スレッドを自動処理するワークフロー。未返信スレッドを抽出し、
3 分類（valid-fix / invalid-reject / needs-human）を行い、修正実装から返信投稿までを一気通貫で実行する。

## ワークフロー概要

```
1. VCS 検出
   ↓
2. 未返信スレッド抽出 (fetch_unanswered.py)
   ↓
3. triage 入力構築 (triage_input_builder.py)
   ↓
4. pr-triage SubAgent → 3 分類
   ↓
5. --dry-run? → dry_run_report.py → PR にサマリコメント → 終了
   ↓ (本番)
6. ユーザー確認 (AskUserQuestion)
   ↓
7. valid-fix → review-fixer SubAgent → 修正実装
   ↓
8. 検証 (verifier.py)
   ↓
9. コミット (committer.py)
   ↓
10. Push (jj safe-push / git push)
    ↓
11. 返信投稿 (post_reply.py, in_reply_to 必須)
    ↓
12. 完了報告
```

## エントリポイント

```
/pr-workflow:respond <PR番号|URL> [--dry-run]
```

手動確認型（レビューを 1 件ずつ確認しながら対応）:
```
/pr-workflow:respond-manual <PR番号|URL>
```

## 返信投稿ルール（失敗パターン対策）

**必ず individual threaded inline reply を使う**:

```bash
# ✅ 正しい: スレッド内への返信
gh api -X POST repos/OWNER/REPO/pulls/NUM/comments \
  -f body='返信内容' \
  -F in_reply_to=ROOT_COMMENT_ID

# ❌ 禁止: PR 本体への general コメント
gh pr comment NUM --body '返信内容'
```

詳細は `references/reply-format.md` を参照。

## 3 分類の基準（概要）

| 分類 | 説明 | 処理 |
|------|------|------|
| valid-fix | バグ/型エラー/プロジェクトルール違反の明確な指摘 | 修正 + 返信 |
| invalid-reject | 対応済み/誤指摘/スコープ外 | 却下理由付きで返信のみ |
| needs-human | 設計判断/意図曖昧/コンテキスト不足 | スキップ、ユーザーに提示 |

詳細は `references/triage-rubric.md` を参照。

## Python スクリプト一覧

全スクリプトは `${CLAUDE_PLUGIN_ROOT}/scripts/` に配置。

### fetch_unanswered.py — 未返信スレッド抽出

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_unanswered.py <PR_URL_or_number>
```

- REST API でインラインコメント取得 + GraphQL で isResolved 確認
- スレッドの最後のコメントが PR 作者またはボットなら除外
- 出力: `{pr, summary, unanswered_threads}` JSON

### triage_input_builder.py — triage 入力構築

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/triage_input_builder.py < fetch_out.json > triage_in.json
```

各スレッドに `root_comment_id`, `latest_comment_body`, `thread_diff_context` を付加。

### post_reply.py — 返信投稿

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/post_reply.py \
  --reply-file /tmp/pr-triage-<PR番号>.json \
  --repo owner/repo
```

- `gh api -X POST .../comments` + `in_reply_to` を使用
- `gh pr comment` は**使用しない**
- `/tmp/pr-replies-posted-<PR番号>.json` で冪等性確保

### build_suggestion.py — suggestion ブロック生成

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/build_suggestion.py \
  --before original.ts --after modified.ts --line 42
```

- single-line suggestion のみ対応（multi-line は空文字を返す）

### dry_run_report.py — dry-run レポート投稿

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/dry_run_report.py \
  --triage-file /tmp/pr-triage-<num>.json --pr <num>
```

- triage 結果を markdown table 化して PR にサマリコメント投稿
- `gh pr comment` の正当な使用箇所（dry-run サマリのみ）

### vcs.py, review_fetcher.py, verifier.py, committer.py, push.py

review-workflow から継承した VCS 操作・コメント取得・検証・コミット・Push スクリプト。
詳細は `references/fix-plan-format.md` と `references/config-example.md` を参照。

## 失敗パターンと対策

詳細は `references/failure-modes.md` を参照。

| 失敗 | 対策 |
|------|------|
| general コメント誤投稿 | `gh pr comment` 禁止、PreToolUse hook で advisory、post_reply.py が in_reply_to 強制 |
| 既返信スレッドへの重複返信 | `/tmp/pr-replies-posted-*.json` で冪等性確保 |
| 解決済みスレッドへの返信 | GraphQL isResolved で事前除外 |
| 作者が返信済みなのに返信 | comments 末尾の author チェックで除外 |

## dry-run モード

```
/auto-respond-pr 123 --dry-run
```

実際の修正・コミット・push・返信投稿を**一切行わず**、実行予定を PR にサマリコメントとして投稿する。
本実行は `--dry-run` を外して再実行する。

## VCS 別の動作

| 操作 | jj | git |
|------|-----|-----|
| コミット | `jj split` + `jj describe` | `git add` + `git commit` |
| Push | `jj safe-push` 経由（未導入時は `jj git push`） | ユーザー確認後に `git push` |
| ブランチ検出 | `jj log` bookmarks | `git branch --show-current` |

## 設定ファイル

プロジェクトの `.claude/review-workflow.local.md` に検証コマンドを定義する。
詳細は `references/config-example.md` を参照。
