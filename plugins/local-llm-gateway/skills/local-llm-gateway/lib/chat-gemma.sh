#!/usr/bin/env bash
# gemma4:26b に Ollama API を直接叩いて問い合わせる。
# claude CLI も LiteLLM proxy も経由しない。claude CLI 経由は起動オーバーヘッドだけで
# 20秒以上かかり、直接呼び出しなら1秒未満で返る(実測値、罠を参照)。
set -euo pipefail

OLLAMA_HOST="${OLLAMA_HOST:-http://localhost:11434}"
# Ollama 自体は OLLAMA_HOST を host:port 形式(スキームなし)で受け取る慣習だが、
# ここでは curl の URL としてそのまま使うため、スキームが無ければ http:// を補う。
# 補わないと "host:port/api/tags" がスキーム無し URL として curl に拒否される。
case "$OLLAMA_HOST" in
  http://*|https://*) ;;
  *) OLLAMA_HOST="http://${OLLAMA_HOST}" ;;
esac
MODEL="${GEMMA_MODEL:-gemma4:26b}"
THINK="${GEMMA_THINK:-false}"
case "$THINK" in
  true|false) ;;
  *)
    echo "GEMMA_THINK は 'true' か 'false' で指定してください: ${THINK}" >&2
    exit 1
    ;;
esac

if ! curl -sf "${OLLAMA_HOST}/api/tags" >/dev/null 2>&1; then
  echo "Ollama に接続できません: ${OLLAMA_HOST}" >&2
  echo "先に 'ollama serve' を実行してください。" >&2
  exit 1
fi

if [ "$#" -gt 0 ]; then
  PROMPT="$*"
else
  PROMPT="$(cat)"
fi

PAYLOAD="$(jq -n --arg model "$MODEL" --arg content "$PROMPT" --argjson think "$THINK" \
  '{model: $model, messages: [{role: "user", content: $content}], stream: false, think: $think}')"

RESPONSE="$(curl -sf "${OLLAMA_HOST}/api/chat" -d "$PAYLOAD")"
if echo "$RESPONSE" | jq -e '.error' >/dev/null 2>&1; then
  echo "Ollama がエラーを返しました: $(echo "$RESPONSE" | jq -r '.error')" >&2
  exit 1
fi
echo "$RESPONSE" | jq -r '.message.content'
