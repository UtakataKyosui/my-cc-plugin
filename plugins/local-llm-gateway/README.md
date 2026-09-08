# local-llm-gateway

Ollama のローカルモデルに直接問い合わせるプラグイン。`claude` CLI を経由しない。

## 構成

| 種別 | 名前 | 役割 |
|---|---|---|
| Skill | `local-llm-gateway:local-llm-gateway` | `gemma` コマンドの使い方と、LiteLLM proxy を使う場合の手順 |

## alias のパスに注意

`gemma` は `lib/chat-gemma.sh` への shell alias である。プラグインのインストール先はバージョンごとにディレクトリが変わるため、`~/.zshrc` に絶対パスを直書きすると次の更新で切れる。安定したパスへの symlink を1つ置いてそこを指す。手順は SKILL.md の「使い方」節にある。

## 依存

- `ollama`（`ollama serve` が起動していること）
- 対象モデルの pull（既定は `gemma4:26b`）
- `jq`
- LiteLLM proxy を使う場合のみ `litellm`
