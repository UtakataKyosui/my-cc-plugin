---
name: budoux-html
description: HTML ファイルの日本語テキストに BudouX の文節境界で <wbr> を入れ、word-break: keep-all の CSS を注入して、単語の途中で改行されないようにする。Markdown の段落結合位置で文節が割れていないかも検査できる。「BudouX で改行を綺麗にして」「日本語の折り返しを直して」と言われたとき、ローカルの HTML レポートを配布する前に使う。CDN を使わずファイル単体で効くようにしたいときの手段。
---

# budoux-html

## 提供するもの

| ファイル | 役割 |
|---|---|
| `budoux_html.py` | HTML を上書きし、日本語を含むテキストノードに `<wbr>` を入れる。`</style>` の直前に改行用 CSS を 1 回だけ注入する |
| `check_md_breaks.py` | Markdown の各行を結合したときに BudouX の文節境界と一致しない箇所を検出する。ソフトラップで生じた不自然な改行を見つける |

## 呼び出し方

```bash
python3 -m venv /tmp/budoux-venv && /tmp/budoux-venv/bin/pip install -q budoux
/tmp/budoux-venv/bin/python "${CLAUDE_PLUGIN_ROOT}/skills/budoux-html/budoux_html.py" path/to/report.html
/tmp/budoux-venv/bin/python "${CLAUDE_PLUGIN_ROOT}/skills/budoux-html/check_md_breaks.py" path/to/doc.md
```

`CLAUDE_PLUGIN_ROOT` はこのプラグインがインストールされたディレクトリを指す。手動で実行するときの実パスは `claude plugin list --json` で確認するか、`find ~/.claude/plugins -path '*/budoux-html/skills/budoux-html/budoux_html.py'` で探す。

## 挙動と罠

- 冪等。実行のたびに既存の `<wbr>` を外してから入れ直すので、本文を編集したあと何度かけてもよい
- `style` `script` `code` `pre` `title` `textarea` `svg` の中は触らない。`<title>` に `<wbr>` を入れると文字として表示されるため
- タグの属性は触らない。`<img src="data:...">` の base64 もそのまま残る
- テキストは一度 `html.unescape` してから分割し、各断片を `html.escape(quote=False)` で戻す。`&amp;` のような実体参照の途中で分割されない
- CSS は `overflow-wrap: break-word` にしている。`anywhere` にすると表の列の最小幅の計算に効いて、列が細く潰れる
- `<style>` がない HTML には CSS を注入しない。その場合は `word-break: keep-all` を自分で足す
- Claude Code プラグイン ja-slop-guard の `BudouxHtml` MCP ツールも `/* ja-slop-guard: budoux */` の印つきで同じ body の指定を入れる。MCP ツールをかけたファイルにこのスクリプトをかけると指定が二重になるため、スクリプトは MCP 側の指定を消してから自分の指定を入れる
- `/tmp/budoux-venv` は `/tmp` の掃除で消える。消えていたら上の呼び出し方の 1 行目で作り直す
- BudouX の分割は完璧ではない。「効果量」が「効果／量」に分かれる例を確認している。英単語のハイフン（`fore-voalt`）はブラウザ側の折り返しで切れる
- CDN の `<budoux-ja>` Web Component を使う方法もあるが、オフラインで開くと効かず、ファイル単体で配布できなくなる

## ja-slop-guard の BudouxHtml MCP ツールとの違い

ja-slop-guard プラグインの `BudouxHtml` MCP ツールも同種の `<wbr>` 挿入と CSS 注入を HTML ファイルに対して行うが、Markdown ファイルの段落結合位置での文節割れは検査しない。`check_md_breaks.py` はこの Markdown 側の検査を担うため、ja-slop-guard を導入していても本プラグインには存在意義がある。HTML の変換だけで足りる場合は、ja-slop-guard がインストール済みなら MCP ツールで代替できる。

## 依存

- Python 3.10 以上、`budoux`（PyPI、0.9.2 で動作確認）
