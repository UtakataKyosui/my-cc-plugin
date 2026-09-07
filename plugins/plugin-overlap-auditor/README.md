# plugin-overlap-auditor

Skill / SubAgent / Command の役割重複を検出し、整理方針を GitHub Issue として記録する監査プラグイン。

## 機能

- **4 スコープを横断した監査**: C2Lab plugins、ユーザーグローバル (`~/.claude/`)、外部マーケットプレイス由来、Claude Code 組み込みコマンド
- **ハイブリッド検出**: Python での静的クラスタリング（Jaccard 類似度 + SequenceMatcher）+ LLM Agent による意味的分類
- **自動 Issue 起票**: 1 クラスタ = 1 Issue、keep/drop/coexist のチェックボックス付き
- **冪等性**: 同一クラスタへの重複起票を防止

## 使い方

```
/audit-overlap                       # 全スコープを dry-run で確認
/audit-overlap --scope=repo          # C2Lab plugins/ のみ
/audit-overlap --post-issues         # 確認後に GitHub Issue を起票
/audit-overlap --post-issues --limit=5   # 最大 5 件だけ起票
```

## 検出できる重複の例

| カテゴリ | 重複例 |
|---|---|
| PR レビュー | code-review/agents/code-reviewer と rust/agents/code-reviewer（同名） |
| jj/VCS | jj-vcs-workflow と harness-toolkit/vcs-jj と グローバル jj-safe-{push,new} |
| Builtin 競合 | plugins/code-review と 組み込み /review が同役割 |
| スクリーンショット | グローバル pr-screenshots と review-screenshots |

## スクリプト直接実行

```bash
# アセット抽出のみ
python3 scripts/extract_assets.py --scope=repo > /tmp/assets.json

# クラスタリングのみ
python3 scripts/cluster_assets.py /tmp/assets.json

# 全工程
python3 scripts/audit_overlap.py --scope=all --summary

# Issue 起票（dry-run）
python3 scripts/post_overlap_issues.py /tmp/clusters.json --dry-run

# builtin manifest のバージョン確認
python3 scripts/update_builtin_manifest.py --check
```

## コンポーネント

| ファイル | 役割 |
|---|---|
| `scripts/extract_assets.py` | 全スコープから frontmatter 抽出 → JSON |
| `scripts/cluster_assets.py` | Jaccard + SequenceMatcher でクラスタリング |
| `scripts/post_overlap_issues.py` | クラスタ → GitHub Issue |
| `scripts/audit_overlap.py` | 上記のオーケストレーター |
| `agents/overlap-classifier.md` | LLM Agent: keep/drop/coexist 判定 |
| `skills/overlap-policy/SKILL.md` | 重複判定ルール集 |
| `data/builtin-commands.json` | Claude Code 組み込みコマンドの静的 manifest |
| `scripts/update_builtin_manifest.py` | builtin manifest のメンテ用スクリプト |

## ローカル検証

```bash
python3 scripts/validate-plugins.py  # プラグイン構造の検証
ruff check plugins/plugin-overlap-auditor/  # lint
```
