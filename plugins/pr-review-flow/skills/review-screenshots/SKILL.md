---
name: review-screenshots
description: PR レビュー時に Playwright MCP で開発サーバーの UI スクリーンショットを撮影し保存する。フォームログイン・Cookie 注入・MSW Route Interception に対応。前提として Playwright MCP がユーザーレベルで設定済みであることを求める。
when_to_use: PR レビュー中に「スクリーンショットを撮って」「UI を確認して」「画面を見せて」「実装の見た目を確認」と指示されたとき。Figma デザインと実装の視覚比較が必要なとき。
argument-hint: "[pr-number]"
allowed-tools: Bash(gh pr diff *) Bash(gh pr view *) Bash(gh pr checkout *) Bash(git stash *) mcp__playwright__browser_navigate mcp__playwright__browser_snapshot mcp__playwright__browser_take_screenshot mcp__playwright__browser_fill_form mcp__playwright__browser_click mcp__playwright__browser_resize mcp__playwright__browser_wait_for mcp__playwright__browser_run_code_unsafe
---

<!-- ja-slop-guard: disable list-heavy bold-label-list bold-density half-colon-space -->

# Review Screenshots

PR レビュー時に Playwright MCP で Web アプリの UI を撮影し、ファイルに保存する。

## 前提条件

- Playwright MCP が `~/.claude.json` の `mcpServers` に設定済み
- `gh` CLI で GitHub にログイン済み
- 保存先ディレクトリ: 環境変数 `REVIEW_SCREENSHOT_DIR`（未設定時は `~/Documents/review-screenshots/`）

## ワークフロー

### Step 1: 対象ページの特定

PR の diff からフロントエンドの変更対象ページを特定する。

```bash
gh pr diff <NUMBER> --name-only
```

ルーティング規約に沿ったファイル（例: `page.tsx`、`+page.svelte` 等）の変更からルートを推定する。
ユーザーが撮影対象を指定しない場合、AskUserQuestion で確認する。

### Step 2: ブランチ切り替え

PR のブランチに切り替える。現在のブランチに未コミットの変更がある場合は `git stash` する。

```bash
gh pr checkout <NUMBER>
```

### Step 3: 開発サーバー起動

ポートを確認し、未起動なら起動する。

```bash
lsof -i :<PORT> | grep LISTEN
```

プロジェクトの AGENTS.md / CLAUDE.md から dev コマンドを確認して起動する。
バックグラウンドで起動し、Ready になるまで待機する。

### Step 4: 認証

1. `browser_navigate` でアプリ URL に遷移
2. `browser_snapshot` でログインページか確認
3. ログインが必要な場合、以下の順で試行:
   - 方法 A（フォームログイン）: モックハンドラー（`**/mocks/**/auth*` を Grep）からテスト認証情報を検索し、`browser_fill_form` + `browser_click` でログインする
   - 方法 B（Cookie 注入）: フォームログインが失敗した場合（MSW ServiceWorker 未起動等）、`browser_run_code_unsafe` で認証 Cookie を直接設定する

Cookie 注入の例:

```javascript
async (page) => {
  await page.context().addCookies([
    {
      name: 'auth-token',
      value: '<JWT>',
      domain: 'localhost',
      path: '/',
    },
  ])
}
```

JWT の構造はモックの認証ハンドラーから読み取る。

### Step 5: スクリーンショット撮影

- ファイル名: `${REVIEW_SCREENSHOT_DIR:-~/Documents/review-screenshots/}review-screenshot-<説明>.png`
- ビューポート全体: `browser_take_screenshot(type: "png", filename: "...")`
- 必要に応じてビューポートをリサイズ: `browser_resize(width, height)`
- メニューやドロップダウン展開時は `browser_click` で開いてから撮影
- 複数ページは `browser_navigate` で遷移して各ページを撮影

### Step 6: 完了報告

撮影したファイルパス一覧をユーザーに報告する。

## MSW が動かない場合の Route Interception

Playwright MCP のブラウザでは MSW の ServiceWorker が登録できない。API リクエストが 404 になる場合、Playwright の `page.route()` で直接モックレスポンスを返す。

手順:
1. `**/mocks/handlers/*.ts` から対象ページが呼ぶ API エンドポイントとモックデータを特定する
2. `browser_run_code_unsafe` で `page.route()` を設定する（ナビゲーション前に設定すること）
3. ルート設定後に `page.goto()` でページに遷移する

```javascript
async (page) => {
  // ナビゲーション前にルートを設定
  await page.route('**/v1/endpoint*', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ /* モックハンドラーのレスポンスデータ */ }),
    });
  });

  // 全ルート設定後にナビゲーション
  await page.goto('http://localhost:3000/target-page', { waitUntil: 'networkidle' });
}
```

対象ページが必要とする全 API（認証、データ取得、フィルター用マスタ等）にルートを設定する。

## 既知の制約

画像アップロードには対応していない。GitHub API は PR コメントへの画像直接アップロードに対応していないため、レビューコメントへの添付は手動で行う。モック環境では Content Security Policy により外部画像がブロックされることがある。「Browser is already in use」エラーが出た場合は Chrome プロセスの競合が原因であり、`pkill -9 -f "chrome.*mcp-chrome"` と SingletonLock ファイルの削除で解消する。

## Figma 比較

Figma MCP が利用可能な場合、`get_screenshot` で Figma デザインのスクリーンショットも取得し、並べて比較できる。

```
get_screenshot(nodeId: "<node-id>")
```

Issue 本文や PR 本文から Figma URL を抽出し、`node-id` パラメータを取得する。
