# PR レビュー対応の失敗パターンと対策

17+ セッションの実績から確認された失敗パターンと、auto-pr-responder での対策。

## 失敗1: general コメント誤投稿

**症状**: `gh pr comment` でスレッド外の PR 本体にコメントを投稿してしまう。
レビュアーには返信として届かず、スレッドが未解決のまま残る。

**対策**:
- `post_reply.py` は `gh api -X POST .../comments -F in_reply_to=ID` のみを使用
- `gh pr comment` は `block-general-comment.sh` (PreToolUse hook) で advisory warning
- dry_run_report.py のサマリコメントのみ `gh pr comment` を許可（dry-run サマリは top-level が正しい）

## 失敗2: 既存スレッド未確認による重複返信

**症状**: 同一スレッドに複数回返信してしまう。
レビュアーが混乱し、重複通知が届く。

**対策**:
- `/tmp/pr-replies-posted-<num>.json` に投稿済みスレッド ID を記録
- `post_reply.py` は起動時にこのファイルを読み込み、済みのスレッドをスキップ
- 冪等性: 再実行しても新たに返信が投稿されない

## 失敗3: 解決済みスレッドへの返信

**症状**: GitHub 上で "Resolved" になっているスレッドに返信してしまう。
不要なスレッドの再開通知が届く。

**対策**:
- `fetch_unanswered.py` が GraphQL `isResolved` フラグで解決済みスレッドを除外
- REST API (`/pulls/.../comments`) では isResolved が取得できないため GraphQL を使用

## 失敗4: PR 作者が返信済みスレッドへの再返信

**症状**: PR 作者がすでに返信しているスレッドに、再度返信してしまう。
「もう返信しましたよ」という状態でさらに返信が届く。

**対策**:
- `fetch_unanswered.py` がスレッドの最後のコメントの author を確認
- PR 作者またはボットアカウントが最後のコメントなら未返信ではないとして除外

## 失敗5: 「修正した」という返信を general comment で投稿

**症状**: `fix: ...` コミット後に PR 全体に「修正しました」とコメント。
インラインスレッドには何も返信されず、レビュアーが対応を見落とす。

**対策**:
- valid-fix の返信は必ず元のスレッドへの `in_reply_to` 返信として投稿
- `post_reply.py` の `reply_draft` は pr-triage が生成したものをそのまま使用

## 失敗6: needs-human を自動修正してしまう

**症状**: 設計判断が必要な指摘を、自動的に実装してしまう。
意図しないアーキテクチャ変更が入る。

**対策**:
- pr-triage agent の判断基準: 迷ったら needs-human に倒す
- validate-triage-output.py が triage JSON のスキーマを検証
- ユーザー確認 (AskUserQuestion) を経てから実装フェーズへ進む

## 失敗7: コメント返信後に push を忘れる

**症状**: コード修正はしたが push を忘れ、CI が古いコードで動き続ける。

**対策**:
- `stop-reminder.sh` (Stop hook) が `/tmp/review-fix-plan-*.json` の存在を確認
- push 前にファイルが残っている場合は警告を表示
- auto-respond-pr のフローでは push (Step 10) の後に返信投稿 (Step 11) を行う順序を強制
