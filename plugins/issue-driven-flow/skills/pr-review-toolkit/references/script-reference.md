# スクリプト詳細仕様

## fetch_pr.py

### 引数

```
fetch_pr.py <PR_REF> [--include-comments] [--no-diff]
```

| 引数 | 説明 |
|------|------|
| `PR_REF` | PR の参照。URL / `owner/repo#N` / 番号のみ（repo 自動検出） |
| `--include-comments` | インラインレビューコメントを `comments[]` に含める |
| `--no-diff` | unified diff を取得しない（高速・軽量化） |

### 出力 JSON 構造

```json
{
  "pr": {
    "number": 123,
    "title": "PR タイトル",
    "body": "PR 説明文",
    "state": "OPEN",
    "is_draft": false,
    "url": "https://github.com/...",
    "head_branch": "feat/foo",
    "base_branch": "main",
    "author": "username",
    "review_decision": "APPROVED",
    "labels": ["bug", "enhancement"],
    "additions": 150,
    "deletions": 30,
    "changed_files": 5,
    "created_at": "2026-01-01T00:00:00Z",
    "updated_at": "2026-01-02T00:00:00Z",
    "merged_at": null
  },
  "files": [
    {
      "path": "src/foo.py",
      "status": "modified",
      "additions": 20,
      "deletions": 5,
      "changes": 25,
      "previous_path": null
    }
  ],
  "diff": "diff --git a/src/foo.py ...\n...",
  "comments": [...]
}
```

`files[].status` の値: `added` / `removed` / `modified` / `renamed` / `copied` / `changed` / `unchanged`

## parse_diff.py

### 入力

- **stdin**: `fetch_pr.py` の JSON 出力をパイプ（`diff` フィールドを読む）
- `--from-fetch <path>`: JSON ファイルから読む
- `--diff-file <path>`: raw unified diff ファイルから読む

### 出力 JSON 構造

```json
{
  "files": [
    {
      "path": "src/foo.py",
      "old_path": "src/foo.py",
      "is_new": false,
      "is_deleted": false,
      "is_binary": false,
      "is_rename": false,
      "hunks": [
        {
          "old_start": 10,
          "old_lines": 5,
          "new_start": 10,
          "new_lines": 7,
          "header": "@@ -10,5 +10,7 @@ def foo():",
          "lines": [
            {"type": "context", "content": "def foo():", "old_no": 10, "new_no": 10},
            {"type": "del",     "content": "    pass",   "old_no": 11},
            {"type": "add",     "content": "    return 1","new_no": 11}
          ]
        }
      ]
    }
  ]
}
```

`lines[].type`: `"add"` / `"del"` / `"context"`

## analyze_pr.py

### 入力

- **stdin**: `fetch_pr.py` の JSON 出力をパイプ
- `--from-fetch <path>`: JSON ファイルから読む

### 出力 JSON 構造

```json
{
  "summary": {
    "total_additions": 150,
    "total_deletions": 30,
    "files_changed": 5,
    "test_files": 2,
    "non_test_files": 3
  },
  "test_ratio": 0.4,
  "by_language": {
    "Python": {"additions": 100, "deletions": 20, "files": 3},
    "YAML":   {"additions": 50,  "deletions": 10, "files": 2}
  },
  "large_files": [
    {"path": "src/big.py", "additions": 300, "deletions": 50}
  ],
  "manifest_changes": [
    {"file": "requirements.txt", "status": "modified"}
  ],
  "warnings": [
    {"type": "credential_pattern", "diff_line": 42, "severity": "high", "snippet": "API_KEY=sk-..."}
  ]
}
```

### warnings の type 一覧

| type | 説明 |
|------|------|
| `credential_pattern` | API_KEY / SECRET 等の認証情報パターン |
| `password_literal` | パスワードのリテラル値 |
| `private_key` | PEM 形式の秘密鍵ヘッダー |
| `aws_access_key` | AWS アクセスキー ID パターン |
| `github_token` | GitHub PAT / ghp_ トークン |
| `sensitive_filename` | `.env` / `credentials.json` 等の機密ファイル変更 |
