#!/usr/bin/env bash
# Issue ごとに git worktree を用意し、herdr のペインで実装エージェントを起動して
# PR の作成までを任せる。1 行 1 Issue の spec ファイルを受け取る。
#
#   run.sh <repo_dir> <owner/repo> <spec_file> [run_dir]
#
# spec の各行: issue|branch|base_branch|extra_prompt_file(省略可)。# で始まる行は無視する
# 結果は <run_dir>/<issue>/result.json、進捗は <run_dir>/status.log に出る。
set -euo pipefail
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
source "${HERDR_FLOW_LIB:-$PLUGIN_ROOT/skills/herdr-fanout/lib/flow.sh}"

REPO_DIR="$1"; GH_REPO="$2"; SPEC="$3"
flow_init
RUN_DIR="${4:-$HOME/.cache/herdr-issue-impl/$FLOW_RUN_ID}"
mkdir -p "$RUN_DIR"
export FLOW_TAB_LOG="$RUN_DIR/tabs.txt"; : >"$FLOW_TAB_LOG"
STATUS="$RUN_DIR/status.log"; touch "$STATUS"
trap flow_cleanup EXIT

WT_ROOT="${ISSUE_IMPL_WT_ROOT:-$(dirname "$REPO_DIR")/$(basename "$REPO_DIR")-wt}"
MODEL="${ISSUE_IMPL_MODEL:-sonnet}"
EFFORT="${ISSUE_IMPL_EFFORT:-high}"
PARALLEL="${ISSUE_IMPL_PARALLEL:-3}"
TIMEOUT_MS="${ISSUE_IMPL_TIMEOUT_MS:-10800000}"
TEMPLATE="${ISSUE_IMPL_TEMPLATE:-$PLUGIN_ROOT/skills/herdr-issue-impl/prompt.tmpl}"
EXTRA_ENV=()
if [ -n "${ISSUE_IMPL_CARGO_TARGET_DIR:-}" ]; then
  # target を共有すると増分キャッシュが worktree ごとに積み上がり、3 並列で 37G に達した
  EXTRA_ENV+=(--env "CARGO_TARGET_DIR=$ISSUE_IMPL_CARGO_TARGET_DIR" --env "CARGO_INCREMENTAL=0")
fi

st() { printf '%s %s\n' "$(date +%H:%M:%S)" "$*" >>"$STATUS"; log "$*"; }

render_prompt() {
  local issue="$1" branch="$2" base="$3" wt="$4" dir="$5" extra="$6"
  sed -e "s|{{ISSUE}}|$issue|g" -e "s|{{BRANCH}}|$branch|g" -e "s|{{BASE}}|$base|g" \
      -e "s|{{WORKTREE}}|$wt|g" -e "s|{{DIR}}|$dir|g" -e "s|{{REPO}}|$GH_REPO|g" "$TEMPLATE"
  if [ -n "$extra" ] && [ -f "$extra" ]; then
    printf '\n## この Issue 固有の補足\n\n'
    cat "$extra"
  fi
  printf '\n## 質問のしかた\n\n'
  flow_agent_ask_instructions "$dir"
}

# 新しい worktree では、親ディレクトリが信頼済みでも Claude Code が信頼の確認を出し、
# herdr agent start は agent_not_ready で返る。確認は利用者がペインで答える。
# スクリプトからキーを送って通すことはしない。
start_agent() {
  local name="$1" pane="$2" waited=0 notified=0
  herdr agent start "$name" --kind claude --pane "$pane" --timeout 60000 -- \
    --model "$MODEL" --effort "$EFFORT" \
    --permission-mode auto --disallowed-tools AskUserQuestion "Bash(herdr:*)" >/dev/null 2>&1 || true
  while [ "$waited" -lt "${ISSUE_IMPL_TRUST_WAIT_S:-1800}" ]; do
    case "$(flow_agent_status "$name")" in
      idle|done) perl -e "select(undef,undef,undef,${FLOW_AGENT_GRACE_MS:-8000}/1000)"; return 0 ;;
    esac
    if [ "$notified" = 0 ] && herdr pane read "$pane" --lines 40 2>/dev/null | grep -q "trust this folder"; then
      st "TRUST $pane $name: ペインで信頼の確認に答えてください"
      notified=1
    fi
    sleep 5; waited=$((waited + 5))
  done
  return 1
}

# done のまま成果物が現れず、working にも戻らない状態を最大 limit_s 秒待つ
wait_idle_done() {
  local name="$1" artifact="$2" limit_s="$3" waited=0
  while [ "$waited" -lt "$limit_s" ]; do
    [ -s "$artifact" ] && return 0
    [ "$(flow_agent_status "$name")" = "done" ] || return 0
    sleep 15; waited=$((waited + 15))
  done
}

run_one() {
  local issue="$1" branch="$2" base="$3" extra="${4:-}"
  local dir="$RUN_DIR/$issue" wt="$WT_ROOT/issue-$issue"
  mkdir -p "$dir"
  if [ ! -d "$wt" ]; then
    git -C "$REPO_DIR" fetch -q origin "$base"
    git -C "$REPO_DIR" worktree add -q -b "$branch" "$wt" "origin/$base"
    st "#$issue worktree 作成: $wt ($branch <- origin/$base)"
  fi
  render_prompt "$issue" "$branch" "$base" "$wt" "$dir" "$extra" >"$dir/prompt.txt"
  local pane name
  pane=$(flow_spawn "issue $issue" "$wt" "${EXTRA_ENV[@]}")
  name="impl-$issue-$FLOW_RUN_ID"
  start_agent "$name" "$pane" || { st "#$issue 起動失敗"; return 1; }
  flow_agent_kick "$name" "$dir/prompt.txt" || { st "#$issue 投入失敗"; return 1; }
  st "#$issue 開始 ($name, pane $pane)"
  local state q nudges=0
  while :; do
    state=$(flow_agent_join "$name" "$TIMEOUT_MS" "$dir/result.json")
    q=$(flow_agent_question "$dir")
    if [ -n "$q" ]; then
      # 親セッションが flow_agent_answer で答えると question.json が消える
      st "#$issue QUESTION $dir/question.json"
      while [ -s "$dir/question.json" ]; do sleep 10; done
      continue
    fi
    [ -s "$dir/result.json" ] && break
    if [ "$state" = "blocked" ]; then
      st "#$issue BLOCKED (pane $pane)"
      while [ "$(flow_agent_status "$name")" = "blocked" ]; do sleep 15; done
      continue
    fi
    # エージェントが自分のバックグラウンド処理を待つあいだターンを閉じると done になる。
    # 完了通知で自動再開することが多いので、しばらく待ってから続きを促す。
    nudges=$((nudges + 1))
    if [ "$nudges" -gt "${ISSUE_IMPL_MAX_NUDGES:-3}" ]; then
      st "#$issue 終了したが result.json が無い (state=$state)"
      return 1
    fi
    st "#$issue result.json 待ち (state=$state, $nudges 回目)"
    wait_idle_done "$name" "$dir/result.json" "${ISSUE_IMPL_RESUME_WAIT_S:-900}"
    [ -s "$dir/result.json" ] && break
    if [ "$(flow_agent_status "$name")" = "done" ]; then
      printf '作業を続けてください。完了したら指示どおり %s/result.json を書いてください。\n' "$dir" >"$dir/nudge.txt"
      flow_agent_kick "$name" "$dir/nudge.txt" || true
    fi
  done
  st "#$issue DONE $(jq -r '.pr_url // "no-pr"' "$dir/result.json")"
}

phase "issues"
pids=()
while IFS='|' read -r issue branch base extra; do
  [ -n "$issue" ] || continue
  case "$issue" in \#*) continue ;; esac
  while [ "$(jobs -rp | wc -l | tr -d ' ')" -ge "$PARALLEL" ]; do sleep 2; done
  ( run_one "$issue" "$branch" "$base" "$extra" ) &
  pids+=("$!")
  sleep 5
done <"$SPEC"
for p in "${pids[@]}"; do wait "$p" || true; done
st "ALL FINISHED"
