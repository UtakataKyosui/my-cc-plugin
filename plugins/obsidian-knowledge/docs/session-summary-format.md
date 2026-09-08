# SessionSummaryの形式

SessionSummaryは、後から知識ノートやZenn記事の素材へ変換できるよう、次の項目を含める。値がない項目は「なし」と書き、推測で補わない。

```markdown
---
type: session-summary
source: session
project: <リポジトリ名>
date: <YYYY-MM-DD>
article_candidate: true | false
---

# <作業タイトル>

## 背景
何に困っていたか。

## 試したこと
試行した方法と結果。

## 判断
採用した方法と、採用しなかった方法の理由。

## 検証
実行したテスト、コマンド、観測結果。

## 再利用できる知識
別のプロジェクトでも使えるルールや注意点。

## Zenn記事の材料
読者に伝えられる主張、対象読者、参考リンク。

## 未解決事項
追加調査や記事化前に確認すること。
```
