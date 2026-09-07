# よくある分析パターン

## PR 全体の概要を素早く把握する

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_pr.py 123 --no-diff \
  | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/analyze_pr.py
```

`--no-diff` で diff 取得をスキップするため高速。変更規模・言語分布・警告の有無を最初に確認する。

## 特定ファイルの変更内容を確認する

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_pr.py 123 \
  | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/parse_diff.py \
  | python3 -c "
import json,sys
data = json.load(sys.stdin)
for f in data['files']:
    if 'auth' in f['path']:
        print(json.dumps(f, indent=2, ensure_ascii=False))
"
```

`parse_diff.py` の出力を jq 相当の Python フィルタで絞り込む。

## レビューコメント付きで全体を把握する

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_pr.py 123 --include-comments \
  | tee /tmp/pr-123.json \
  | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/analyze_pr.py
```

`/tmp/pr-123.json` に全データを保存しながら分析結果を得る。後続で `parse_diff.py` に渡せる。

## 秘密情報・セキュリティ警告だけを確認する

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_pr.py 123 \
  | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/analyze_pr.py \
  | python3 -c "
import json,sys
result = json.load(sys.stdin)
warnings = result.get('warnings', [])
if warnings:
    print(json.dumps(warnings, indent=2, ensure_ascii=False))
else:
    print('No security warnings detected.')
"
```

## 依存関係の変更を確認する

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_pr.py 123 --no-diff \
  | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/analyze_pr.py \
  | python3 -c "
import json,sys
result = json.load(sys.stdin)
for m in result.get('manifest_changes', []):
    print(m['file'], ':', m['status'])
"
```

## テストカバレッジの確認

`test_ratio` が 0 に近い場合はテストなしで機能追加している可能性がある。

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_pr.py 123 --no-diff \
  | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/analyze_pr.py \
  | python3 -c "
import json,sys
result = json.load(sys.stdin)
ratio = result['test_ratio']
summary = result['summary']
print(f'Test ratio: {ratio:.1%}')
print(f'Test files: {summary[\"test_files\"]} / {summary[\"files_changed\"]}')
if ratio < 0.1 and summary['non_test_files'] > 2:
    print('WARNING: Few or no test files in this PR.')
"
```

## 大規模変更ファイルの特定

```bash
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_pr.py 123 --no-diff \
  | python3 ${CLAUDE_PLUGIN_ROOT}/scripts/analyze_pr.py \
  | python3 -c "
import json,sys
result = json.load(sys.stdin)
for f in sorted(result['large_files'], key=lambda x: x['additions']+x['deletions'], reverse=True):
    total = f['additions'] + f['deletions']
    print(f\"{total:4d} lines  +{f['additions']} -{f['deletions']}  {f['path']}\")
"
```

## fetch 結果をファイルに保存して複数回参照する

```bash
# 一度だけ取得してファイルに保存
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/fetch_pr.py 123 > /tmp/pr-123.json

# 分析（gh 呼び出しなし）
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/analyze_pr.py --from-fetch /tmp/pr-123.json

# diff 構造化（gh 呼び出しなし）
python3 ${CLAUDE_PLUGIN_ROOT}/scripts/parse_diff.py --from-fetch /tmp/pr-123.json
```

API 呼び出しを最小化したい場合に有効。
