---
name: mac-window-capture
description: macOS で特定アプリのウィンドウだけをスクリーンショットに撮る。画面全体や矩形指定と違い、手前に重なった他アプリのウィンドウが写り込まない。デスクトップアプリの動作確認、GUI の目視検証、機密情報を含む画面を開いたまま特定アプリだけを記録したいときに使う。
---

# macOS で1つのウィンドウだけを撮る

`screencapture -x out.png` は画面全体を撮る。`-R x,y,w,h` は矩形を撮るが、その矩形に
重なっている他アプリのウィンドウも一緒に写る。作業中の端末やチャットが写り込むため、
検証用のスクリーンショットには使えない。

`screencapture -l <CGWindowID>` は指定したウィンドウだけを撮る。重なっている他の
ウィンドウは写らない。ウィンドウが他のウィンドウに隠れていても撮れる。

## 使い方

`CLAUDE_PLUGIN_ROOT` はこのプラグインがインストールされたディレクトリを指す。手動で実行するときの実パスは `claude plugin list --json` で確認するか、`find ~/.claude/plugins -path '*/mac-window-capture/skills/mac-window-capture/window-id.swift'` で探す。

```bash
ID=$(swift "${CLAUDE_PLUGIN_ROOT}/skills/mac-window-capture/window-id.swift" "Safari")
screencapture -x -o -l"$ID" ~/Desktop/app.png
```

`window-id.swift` の引数はプロセスの表示名である。`.app` の名前と一致する。
分からない場合は次で一覧を出す。

```bash
osascript -e 'tell application "System Events" to get name of every process whose visible is true'
```

| フラグ | 意味 |
|---|---|
| `-x` | 撮影音を鳴らさない |
| `-o` | ウィンドウの影を含めない。余白が減る |
| `-l<id>` | 撮る対象のウィンドウ |

## 実測で分かったこと

`screencapture -R` は座標をポイントで受け取り、出力は Retina のデバイスピクセルになる。
`-R 0,30,920,900` を渡すと 1840x1817 の画像が出る。倍率を取り違えて別の場所を撮り、
無関係なアプリの内容を記録してしまう事故が起きやすい。範囲を指定したいときでも `-l` を使う。

`CGWindowListCopyWindowInfo` の一覧は手前のウィンドウから順に並ぶ。`kCGWindowLayer` が 0 の
ものが通常のウィンドウで、影やツールチップは別のレイヤーに現れる。両方を絞らないと
実体のないウィンドウの id を拾う。

アプリを `cargo run` のようにバンドルの外から起動すると、macOS はそれを補助的なプロセスと
みなす。この状態では `System Events` の `count of windows` が 0 を返し、アクセシビリティ
経由の操作ができない。`CGWindowListCopyWindowInfo` からは見えるため撮影はできる。
アクセシビリティで操作したい場合は `.app` バンドルを作って起動する。

`System Events` の `click at {x, y}` は環境によって `-25208` で失敗する。要素を辿って
`click (button 1 of group 2 of ...)` と書くほうが安定する。Web ビューの中身も、要素に
`role="button"` と `tabIndex` が付いていればボタンとして辿れる。

WebView のアクセシビリティツリーには、画面に見えている範囲しか現れない。スクロールしないと
見えない要素は `entire contents` を取っても出てこない。

## 依存

- `swift`（Xcode Command Line Tools に含まれる）
- `screencapture`（macOS 標準）
- 対象アプリを操作する場合は、呼び出し元のターミナルにアクセシビリティの権限が要る
