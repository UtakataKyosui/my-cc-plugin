# PR レビュー返信フォーマット

## 基本ルール

PR レビューコメントへの返信は必ず **individual threaded inline reply** を使う。

### ✅ 正しい: gh api -X POST + in_reply_to

```bash
gh api -X POST repos/OWNER/REPO/pulls/PR_NUMBER/comments \
  -f body='返信内容（suggestion ブロック含む場合もあり）' \
  -F in_reply_to=ROOT_COMMENT_ID
```

- `ROOT_COMMENT_ID`: スレッドの最初のコメントの `id`（thread_id と同じ）
- これにより GitHub 上でスレッド内の返信として表示される

### ❌ 禁止: gh pr comment

```bash
# NG - PR 本体への general コメントになる
gh pr comment NUM --body '返信内容'
```

`gh pr comment` はスレッド外の PR 全体コメントになるため、レビュー返信には使用しない。
唯一の例外: dry_run_report.py が dry-run サマリを投稿する場合。

## suggestion ブロック

コード修正提案を返信に含める場合は GitHub suggestion 記法を使う。

````markdown
ご指摘ありがとうございます。以下のように修正しました。

```suggestion
const result = items.filter(Boolean);
```
````

- suggestion ブロックは build_suggestion.py で自動生成する
- single-line のみ対応（multi-line は needs-human に分類）
- suggestion ブロックを含む場合は `reply_draft` + `suggestion_block` を連結する

## reply_draft の書き方

### valid-fix（修正あり）

```
ご指摘ありがとうございます。型アノテーションを修正しました。
```

または英語:

```
Thanks for the feedback. Fixed the type annotation.
```

### invalid-reject（却下）

```
ご確認ありがとうございます。この変更は既に適用済みです（コミット abc1234 で修正済み）。
```

却下理由を具体的に記載する。一方的な拒絶ではなく、技術的根拠を示す。

### 言語

スレッド内のコメントと同じ言語（日本語/英語）で返信する。
混在している場合は最後のコメントの言語に合わせる。
