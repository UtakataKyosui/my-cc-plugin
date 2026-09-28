---
name: mermaid-render-probe
description: Mermaid の図を実ブラウザでレンダーして、生成された SVG の実寸・テーマ変数の効き・ラベルのはみ出しを実測する。jsdom では Mermaid の gantt が描画できない（getBBox 未実装）ため、ユニットテストで確かめられない描画結果を確認したいときに使う。Mermaid の設定値（leftPadding・useMaxWidth 等）を変えて挙動を比較したいときにも使う。
---

# Mermaid の描画結果を実ブラウザで実測する

## いつ使うか

- Mermaid が出力する SVG の実寸・属性（`width` / `viewBox` / インライン `style`）を知りたい
- `themeVariables` が実際にどの要素へ効くか確かめたい
- ラベルが図の外にはみ出して切れていないか測りたい
- `gantt.leftPadding` のような設定値を振って結果を比較したい

## 実測でわかっている罠

- **jsdom では Mermaid の gantt がレンダーできない**。`drawRects` が `this.getBBox()` を呼び、jsdom は SVGElement にこれを実装していないため `TypeError: this.getBBox is not a function` で落ちる。したがって vitest 環境の中では描画結果を検証できず、テストでは `vi.mock("mermaid")` するしかない。描画そのものの確認はこのスキルで行う
- **`useMaxWidth: false` にすると、SVG からインライン `style` が消え `width` に実数値が入る**。`max-width` を剥がす処理を書く場合、この状態も通ることを確認する
- **gantt の自然幅は描画時に使える幅から決まる**（ビューポート 1000px → SVG 幅 1000px）。固定値ではない
- **`themeVariables` には解決済みの色を渡す**。`var(--x)` のような文字列は Mermaid 内部の lighten/darken 演算で壊れる
- **バーより長いラベルは、収まらなければバーの左側に置かれ、図の左端(x=0)より外は無言で切れる**。`ganttDiagram` の該当箇所は `endX + textWidth + 1.5 * conf.leftPadding > w` で左右を切り替えている

## 使い方

`node_modules/mermaid` を持つリポジトリのルートで静的サーバを立て、`probe.html` をそこへ置いて開く。`CLAUDE_PLUGIN_ROOT` はこのプラグインがインストールされたディレクトリを指す。手動で実行するときの実パスは `claude plugin list --json` で確認するか、`find ~/.claude/plugins -path '*/mermaid-render-probe/skills/mermaid-render-probe/probe.html'` で探す。

```bash
cd <repo with node_modules/mermaid>
cp "${CLAUDE_PLUGIN_ROOT}/skills/mermaid-render-probe/probe.html" .
python3 -m http.server 8899 >/dev/null 2>&1 &
```

`config` と `def` を URL パラメータに JSON で渡す。

```
http://localhost:8899/probe.html?config=<encodeURIComponent(JSON)>&def=<encodeURIComponent(JSON array of lines)>
```

Playwright MCP などで `window.__probe` を読む。返る値:

| キー | 意味 |
|---|---|
| `viewBox` | `minX` と `width` |
| `svgWidth` | ルート `<svg>` の `width` 属性 |
| `clippedLeft` / `clippedRight` | viewBox の外に出ている `<text>`（内容と左右座標） |
| `worstLeftOverflow` | 左方向の最大はみ出し量（0 なら切れていない） |

後片付け: `probe.html` を消し、サーバを `kill $(lsof -ti:8899)` で止める。リポジトリに `probe.html` をコミットしない。
