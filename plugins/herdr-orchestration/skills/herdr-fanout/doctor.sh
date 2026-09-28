#!/usr/bin/env bash
# doctor.sh — herdr 上でエージェントを並列展開する配管が動くかを自己診断する。
#
# 使い方:
#   doctor.sh [--kind claude] [--keep-panes] [--skip-relay]
#
# 検査する順序は flow.sh を使うスクリプトと同じ。
#   依存 -> タブ作成 -> シェル準備 -> エージェント起動 -> プロンプト投入 -> ファイル契約
#   -> 専用ワークスペース -> 質問の中継 -> 後片付け
# 最後の2段はエージェントを2ターン動かすため時間がかかる。--skip-relay で飛ばせる。
# どの段で落ちたかが分かるため、ファンアウトするスクリプトが動かないときは
# 個別スクリプトを疑う前にこれを実行する。

set -uo pipefail

# shellcheck source=lib/flow.sh
source "${HERDR_FANOUT_LIB:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/flow.sh}"

KIND="claude"
SKIP_RELAY=0
while [ $# -gt 0 ]; do
  case "$1" in
    --kind) KIND="$2"; shift 2 ;;
    --keep-panes) export FLOW_KEEP_PANES=1; shift ;;
    --skip-relay) SKIP_RELAY=1; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) flow_die "不明なオプション: $1" ;;
  esac
done

PASS=0
FAIL=0
check() {
  local label="$1" ok="$2" detail="${3:-}"
  if [ "$ok" = "1" ]; then
    printf '  \033[32mOK\033[0m   %s %s\n' "$label" "$detail" >&2
    PASS=$((PASS + 1))
  else
    printf '  \033[31mNG\033[0m   %s %s\n' "$label" "$detail" >&2
    FAIL=$((FAIL + 1))
  fi
}

phase "依存とコンテキスト"
flow_init
check "herdr / jq / gh と HERDR_ENV" 1 "run_id=$FLOW_RUN_ID"
check "呼び出し元の workspace を特定できる" \
  "$([ -n "${HERDR_WORKSPACE_ID:-}" ] && echo 1 || echo 0)" "workspace=${HERDR_WORKSPACE_ID:-未設定}"

D=$(mktemp -d)
export FLOW_TAB_LOG="$D/tabs.txt"; : >"$FLOW_TAB_LOG"
trap flow_cleanup EXIT
OUT="$D/doctor-out.json"

phase "タブ作成とシェル準備"
PANE=""
# cwd に一時ディレクトリを渡さない。新しいディレクトリで Claude Code を起動すると
# フォルダを信頼するかの確認が出て blocked のまま止まる。成果物のパスは絶対パスで
# 渡すため、cwd は呼び出し元のままでよい。実測でこれを踏んだ。
if PANE=$(flow_spawn "doctor" "$PWD" 2>/dev/null); then
  check "tab create と前景シェルの待ち合わせ" 1 "pane=$PANE"
  actual_ws="${PANE%%:*}"
  check "自分の workspace にタブができた" \
    "$([ "$actual_ws" = "${HERDR_WORKSPACE_ID:-}" ] && echo 1 || echo 0)" \
    "作成先=$actual_ws 期待=${HERDR_WORKSPACE_ID:-}"
else
  check "tab create と前景シェルの待ち合わせ" 0 "flow_spawn が失敗した"
  phase "結果"; printf '  合格 %s / 不合格 %s\n' "$PASS" "$FAIL" >&2; exit 1
fi

phase "エージェント起動"
NAME="doctor-$FLOW_RUN_ID"
if flow_agent_start "$NAME" "$KIND" "$PANE" -- --allowed-tools Read Write 2>/dev/null; then
  check "agent start（${KIND}）" 1 "name=$NAME"
else
  check "agent start（${KIND}）" 0 "herdr integration status で $KIND のフックを確認する"
  phase "結果"; printf '  合格 %s / 不合格 %s\n' "$PASS" "$FAIL" >&2; exit 1
fi

phase "プロンプト投入とファイル契約"
printf 'Write ツールで %s に {"ok":true} だけを書き、最後の返答はそのパスだけにしてください。他のことは何もしないでください。\n' "$OUT" >"$D/prompt.txt"
if flow_agent_kick "$NAME" "$D/prompt.txt" >/dev/null 2>&1; then
  check "プロンプトが届いた" 1
else
  check "プロンプトが届いた" 0 "FLOW_AGENT_GRACE_MS と FLOW_KICK_WAIT_MS を増やす"
fi

# 成果物のパスを渡して join する。これが flow_agent_join の誤検知の回帰検出に
# なる。--until を落とすと投入直後の idle で抜けるため、この時点で $OUT が
# まだ存在せず次のチェックが落ちる。
STATE=$(flow_agent_join "$NAME" "${FLOW_DOCTOR_TIMEOUT_MS:-300000}" "$OUT")
settled=0
case "$STATE" in done|blocked) settled=1 ;; esac
check "done まで待てた" "$settled" "state=$STATE（idle で返るなら agent wait の --until が落ちている）"

if [ -s "$OUT" ] && jq -e '.ok' "$OUT" >/dev/null 2>&1; then
  check "エージェントがファイルに結果を書いた" 1 "$(tr -d '\n' <"$OUT")"
else
  check "エージェントがファイルに結果を書いた" 0 "ペイン末尾を保存した: $D/tail.txt"
  herdr agent read "$NAME" --source recent-unwrapped --lines 60 >"$D/tail.txt" 2>&1 || true
fi

if [ "$SKIP_RELAY" = "1" ]; then
  phase "結果"
  printf '  合格 %s / 不合格 %s\n' "$PASS" "$FAIL" >&2
  printf '  作業ディレクトリ: %s\n' "$D" >&2
  [ "$FAIL" -eq 0 ]
  exit
fi

phase "専用ワークスペースと質問の中継"
# ここから先は flow_workspace_create で作成先を切り替える。前段の
# 「自分の workspace にタブができた」の検査より後に置くこと。
WS=""
# command substitution で呼ばない。サブシェルになると FLOW_WORKSPACE が伝わらない。
if flow_workspace_create "doctor-relay-$FLOW_RUN_ID" >/dev/null 2>&1; then
  WS="$FLOW_WORKSPACE"
  check "workspace create（--no-focus）" 1 "workspace=$WS"
else
  check "workspace create（--no-focus）" 0 "flow_workspace_create が失敗した"
fi

RELAY_D="$D/relay"
mkdir -p "$RELAY_D"
RELAY_OUT="$RELAY_D/result.json"
PANE2=""
if [ -n "$WS" ] && PANE2=$(flow_spawn "doctor-relay" "$PWD" 2>/dev/null); then
  check "専用ワークスペースにタブができた" \
    "$([ "${PANE2%%:*}" = "$WS" ] && echo 1 || echo 0)" \
    "作成先=${PANE2%%:*} 期待=$WS"
else
  check "専用ワークスペースにタブができた" 0 "flow_spawn が失敗した"
fi

if [ -n "$PANE2" ]; then
  NAME2="doctor-relay-$FLOW_RUN_ID"
  # AskUserQuestion を実際に禁止する。禁止せずに「使えません」と伝えると、
  # ペイン側が嘘の制約を課すプロンプトインジェクションだと判定して拒否する。
  if flow_agent_start "$NAME2" "$KIND" "$PANE2" -- \
      --allowed-tools Read Write --disallowed-tools AskUserQuestion 2>/dev/null; then
    check "中継用エージェントの起動" 1 "name=$NAME2"

    {
      printf 'これは herdr-fanout の質問中継の動作確認です。次の手順を実行してください。\n\n'
      flow_agent_ask_instructions "$RELAY_D"
      printf '\n確認したいのは中継そのものなので、質問の内容は何でも構いません。\n'
      printf '「合言葉は何ですか」を question.json に書いて、いったん応答を終えてください。\n'
      printf '再開の指示を受けて answer.json を読んだら、そこにあった回答の文字列を\n'
      printf '{"answer":"<読み取った文字列>"} の形で %s に書いてください。\n' "$RELAY_OUT"
      printf '最後の返答はそのパスだけにしてください。\n'
    } >"$RELAY_D/prompt.txt"

    flow_agent_kick "$NAME2" "$RELAY_D/prompt.txt" >/dev/null 2>&1
    flow_agent_join "$NAME2" "${FLOW_DOCTOR_TIMEOUT_MS:-300000}" >/dev/null

    Q=$(flow_agent_question "$RELAY_D")
    if [ -n "$Q" ]; then
      check "ペイン側が質問をファイルへ書いた" 1 "$(printf '%s' "$Q" | jq -r '.question' 2>/dev/null)"
    else
      herdr agent read "$NAME2" --source recent-unwrapped --lines 80 >"$RELAY_D/ask-tail.txt" 2>&1 || true
      check "ペイン側が質問をファイルへ書いた" 0 "ペイン末尾を保存した: $RELAY_D/ask-tail.txt"
    fi

    if [ -n "$Q" ] && flow_agent_answer "$NAME2" "$RELAY_D" "やまびこ"; then
      check "回答を書いて再開させた" 1
      [ -f "$RELAY_D/question.json" ] \
        && check "回答後に question.json を消した" 0 "残っている" \
        || check "回答後に question.json を消した" 1
      flow_agent_join "$NAME2" "${FLOW_DOCTOR_TIMEOUT_MS:-300000}" >/dev/null
      if [ -s "$RELAY_OUT" ] && [ "$(jq -r '.answer' "$RELAY_OUT" 2>/dev/null)" = "やまびこ" ]; then
        check "ペイン側が回答を読んで続きを実行した" 1
      else
        check "ペイン側が回答を読んで続きを実行した" 0 "ペイン末尾を保存した: $RELAY_D/tail.txt"
        herdr agent read "$NAME2" --source recent-unwrapped --lines 60 >"$RELAY_D/tail.txt" 2>&1 || true
      fi
    else
      check "回答を書いて再開させた" 0 "flow_agent_answer が失敗した"
    fi
  else
    check "中継用エージェントの起動" 0 "herdr integration status を確認する"
  fi
fi

phase "結果"
printf '  合格 %s / 不合格 %s\n' "$PASS" "$FAIL" >&2
printf '  作業ディレクトリ: %s\n' "$D" >&2
[ "$FAIL" -eq 0 ]
