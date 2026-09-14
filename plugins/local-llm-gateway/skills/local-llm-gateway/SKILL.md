---
name: local-llm-gateway
description: >-
  Ollamaのローカルモデル(gemma4:26b等)に直接問い合わせる専用コマンド gemma を提供する。
  Claude Code(claude CLI)は経由しない。通常の claude コマンド(Sonnet/Opus/Fable、
  サブスクリプション課金)には一切影響しない。
  「ローカルLLMを使いたい」「gemma に質問したい」と言われたときに使う。
---

# local-llm-gateway

## 背景・制約

当初はLiteLLM proxyでOllamaをAnthropic API互換に見せかけ、`claude` CLIから
`gemma4-26b` を選ぶ方式を採っていた。実測したところ、単純な一問一答でも
claude CLI経由は約23.5秒かかり、そのうち約21秒はCLIの起動・認証・
auto-compact判定などのオーバーヘッドで、モデルの推論そのものではなかった。
Claude Codeのツール呼び出し(tool_use)やセッション管理を使わない用途なら
CLIを経由する理由がないため、Ollamaの `/api/chat` を直接叩く方式に変更した。

もう一つの遅延要因はモデル自身の内部思考(thinking/CoT)である。gemma4:26bは
単純な質問でも数千文字規模の思考テキストを最終回答の前に生成しており、これが
約8秒かかっていた。Ollamaの `think: false` オプションで無効化すると1秒未満まで
短縮される。`lib/chat-gemma.sh` はデフォルトで `think: false` を渡す。

LiteLLM proxy(`config.yaml` / `lib/start-proxy.sh`)は、Claude Code以外の
Anthropic API互換ツールからgemmaを呼びたくなった場合のために残してあるが、
通常の利用では不要である。

## 構成ファイル

| ファイル | 役割 |
|---|---|
| `lib/chat-gemma.sh` | Ollamaの `/api/chat` に直接問い合わせるスクリプト。`gemma` alias の実体 |
| `config.yaml` | (オプション)LiteLLM proxyのモデル定義。`keep_alive: "24h"` でモデルをメモリに常駐させる |
| `lib/start-proxy.sh` | (オプション)LiteLLM proxyを起動する。Anthropic API互換ツールから呼びたい場合のみ使う |
| `doctor.sh` | Ollama起動・モデルpull・proxy疎通を診断する |
| `~/Library/LaunchAgents/com.local-llm-gateway.litellm.plist` | (オプション)proxyをログイン時に自動起動するlaunchd設定(リポジトリ外) |

## 使い方

初回セットアップ:

```bash
ollama serve &                      # 未起動なら
ollama pull gemma4:26b              # 未pullなら
```

シェルのaliasに追加する。プラグインのインストール先はバージョンごとにディレクトリが
変わるため、alias に直書きすると次の更新で切れる。安定したパスへの symlink を1つ置いて
そこを指す。

```bash
ln -sfn "$CLAUDE_PLUGIN_ROOT/skills/local-llm-gateway/lib/chat-gemma.sh" \
  ~/.local/bin/chat-gemma.sh
# ~/.zshrc
alias gemma='bash ~/.local/bin/chat-gemma.sh'
```

`$CLAUDE_PLUGIN_ROOT` はエージェントのセッション内でしか展開されないため、symlink の
張り替えはエージェントに依頼するか、`claude plugin` の出力からパスを確認して手で行う。

以後:

```bash
gemma "日本の首都はどこですか？"     # 引数をそのままプロンプトにする
echo "要約してほしい文章" | gemma   # 標準入力からも渡せる
```

モデルを変えたい場合は環境変数で上書きする。

```bash
GEMMA_MODEL="gemma4:e4b" gemma "軽量モデルで試す"
GEMMA_THINK=true gemma "思考過程も見たい場合"
```

## 罠(実測)

- **claude CLI経由はオーバーヘッドが大きい**。単純な一問一答で約23.5秒かかり、うち約21秒はCLI起動・認証・auto-compact判定などで、モデル推論とは無関係だった。ツール呼び出しやセッション管理が不要ならOllamaを直接叩く
- **gemma4:26bは内部思考(CoT)を大量に生成する**。`think` を指定しないと単純な質問でも約8秒かかる。`think: false` を渡すと1秒未満になる
- **`ollama/<model>` ではなく `ollama_chat/<model>` を使う**(proxy利用時のみ関係)。`ollama/` はOllamaの `/api/generate` を叩くためツール呼び出し(function calling)を返さない。`ollama_chat/` は `/api/chat` を使いツール呼び出しに対応する
- `keep_alive` を設定しないと、リクエストのたびにモデルの再ロードが走る。`config.yaml` で `keep_alive: "24h"` を設定するか、`chat-gemma.sh` から直接叩く場合もOllama側に一度ロードされたモデルは同じ時間残り続ける
- `pip install litellm[proxy]` はHomebrew PythonのPEP 668制約でブロックされる。proxyを使う場合は `pipx install 'litellm[proxy]'` を使う

## 依存

- `ollama`(起動済み、対象モデルpull済み)
- `curl`, `jq`
- (オプション、proxy利用時のみ) `litellm[proxy]`(`pipx install 'litellm[proxy]'`)、`openssl`
