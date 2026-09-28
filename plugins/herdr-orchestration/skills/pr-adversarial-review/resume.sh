#!/usr/bin/env bash
# resume.sh — collect.sh が途中で落ちたランを、残っている成果物から再開する。
#
# 使い方:
#   resume.sh <RUN_DIR> <PR番号...> [--kind claude] [--keep-panes]
#
# findings.json があり verdicts.json が無い PR について、反証者だけを立て直し、
# plan.json と plans.json と plan.md を作り直す。レビュワーは再実行しない。
#
# 想定する失敗: flow_agent_join がタイムアウト前に state=working のまま返り、
# collect.sh が findings.json 未生成と判定して打ち切ったあと、レビュワーが
# 遅れて findings.json を書き終えているケース。実測でこれを踏んだ。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
# shellcheck source=../herdr-fanout/lib/flow.sh
source "${HERDR_FANOUT_LIB:-$PLUGIN_ROOT/skills/herdr-fanout/lib/flow.sh}"
# shellcheck source=../agent-routing/lib/routing.sh
source "${AGENT_ROUTING_LIB:-$PLUGIN_ROOT/skills/agent-routing/lib/routing.sh}"

RUN_DIR=""
KIND="claude"
PRS=()
export FLOW_KEEP_PANES=0

while [ $# -gt 0 ]; do
  case "$1" in
    --kind) KIND="$2"; shift 2 ;;
    --keep-panes) FLOW_KEEP_PANES=1; shift ;;
    -h|--help) sed -n '2,14p' "$0"; exit 0 ;;
    -*) flow_die "不明なオプション: $1" ;;
    *) if [ -z "$RUN_DIR" ]; then RUN_DIR="$1"; else PRS+=("$1"); fi; shift ;;
  esac
done

[ -n "$RUN_DIR" ] && [ -d "$RUN_DIR" ] || flow_die "RUN_DIR が無い: $RUN_DIR"
[ "${#PRS[@]}" -gt 0 ] || flow_die "再開する PR 番号を1つ以上渡す"

flow_init
REPO="${PRAR_REPO:-$(gh repo view --json nameWithOwner -q .nameWithOwner)}"
ISSUE_POLICY="${PRAR_ISSUE_POLICY:-suggest}"

export FLOW_TAB_LOG="$RUN_DIR/tabs.txt"
TIMING_FILE="$RUN_DIR/timing.jsonl"
trap flow_cleanup EXIT

render_prompt() {
  local template="$1" pr="$2" findings="$3" verdicts="$4"
  sed -e "s|__REPO__|$REPO|g" \
      -e "s|__PR__|$pr|g" \
      -e "s|__FINDINGS__|$findings|g" \
      -e "s|__VERDICTS__|$verdicts|g" \
      "$SCRIPT_DIR/prompts/$template"
}

resume_pr() {
  local pr="$1"
  local dir="$RUN_DIR/pr-$pr"
  local findings="$dir/findings.json" verdicts="$dir/verdicts.json"

  [ -s "$findings" ] && jq -e '.findings' "$findings" >/dev/null 2>&1 \
    || { log "#$pr: findings.json が無いか壊れている。レビューからやり直す必要がある"; return 1; }

  local n
  n=$(jq '.findings | length' "$findings")
  log "#$pr: 既存の指摘 $n 件を再利用する"

  if [ ! -s "$verdicts" ] || ! jq -e '.verdicts' "$verdicts" >/dev/null 2>&1; then
    if [ "$n" -gt 0 ]; then
      local ref="ref-$pr-$FLOW_RUN_ID" pane t0 t1 state
      pane=$(flow_spawn "refute #$pr" "$PWD") || return 1
      t0=$(date +%s)
      flow_agent_start_role "$ref" refute "$pane" "$KIND" || { log "#$pr: 検証者の起動に失敗"; return 1; }
      render_prompt refuter.md "$pr" "$findings" "$verdicts" >"$dir/refuter-prompt.txt"
      flow_agent_kick_role "$ref" "$dir/refuter-prompt.txt" refute || true
      state=$(flow_agent_join "$ref" "${PRAR_TIMEOUT_MS:-1800000}" "$verdicts")
      t1=$(date +%s)
      flow_record_timing "$TIMING_FILE" refute "$ref" "pr-$pr" "$t0" "$t1" "$state"
      log "#$pr: 検証完了状態=$state"
      if [ ! -s "$verdicts" ] || ! jq -e '.verdicts' "$verdicts" >/dev/null 2>&1; then
        log "#$pr: verdicts.json が得られなかった。全件を未検証として保留する"
        herdr agent read "$ref" --source recent-unwrapped --lines 200 >"$dir/refuter-tail.txt" 2>/dev/null || true
        printf '{"pr":%s,"verdicts":[]}\n' "$pr" >"$verdicts"
      fi
    else
      printf '{"pr":%s,"verdicts":[]}\n' "$pr" >"$verdicts"
    fi
  else
    log "#$pr: verdicts.json は既にある。反証は再実行しない"
  fi

  jq -n --slurpfile f "$findings" --slurpfile v "$verdicts" --arg issue_policy "$ISSUE_POLICY" '
    ($f[0]) as $F
    | ($v[0].verdicts // []) as $Vraw
    | ($Vraw | group_by(.id) | map(.[0]) | INDEX(.id)) as $V
    | ($F.findings // []) as $items
    | [ $items[] | . as $it | ($V[$it.id]) as $vd
        | $it + { verdict: $vd, effective_scope: ($vd.scope_override // $it.scope) } ] as $judged
    | {
        pr: $F.pr, pr_title: $F.pr_title,
        linked_issues: ($F.linked_issues // []),
        scope_summary: ($F.scope_summary // ""),
        good_points: ($F.good_points // []),
        issue_policy: $issue_policy,
        confirmed: [ $judged[] | select(.verdict.refuted == false) ],
        refuted:   [ $judged[] | select(.verdict.refuted == true) ],
        unverified: [ $items[] | select( $V[.id] == null ) ]
      }
    | . + {
        inline_comments: [ .confirmed[]
          | select(.effective_scope == "in-scope")
          | select((.review_comment // "") != "")
          | select(.verdict.line_valid != false)
          | {path, line, severity, id, body: .review_comment} ],
        out_of_scope: [ .confirmed[]
          | select(.effective_scope == "out-of-scope")
          | select((.issue_title // "") != "")
          | {id, title: .issue_title, body: .issue_body, severity, path, line} ]
      }
  ' >"$dir/plan.json"
  log "#$pr: 起案完了 -> $dir/plan.json"
}

phase "Resume (${#PRS[@]} PR)"
for pr in "${PRS[@]}"; do resume_pr "$pr" || true; done

phase "Summary"
export REPO FLOW_RUN_ID
jq -s '{repo: env.REPO, run_id: env.FLOW_RUN_ID, plans: .}' "$RUN_DIR"/pr-*/plan.json >"$RUN_DIR/plans.json" 2>/dev/null \
  || flow_die "plan.json が 1 つも生成されなかった。$RUN_DIR を確認する"

{
  printf '# 敵対的レビュー結果 (%s / run %s)\n\n' "$REPO" "$FLOW_RUN_ID"
  jq -r '.plans[] |
    "## #\(.pr) \(.pr_title)\n",
    "スコープ: \(.scope_summary)\n",
    "Issue 方針: \(.issue_policy)\n",
    "投稿予定のインラインコメント: \(.inline_comments | length) 件",
    "スコープ外(out_of_scope): \(.out_of_scope | length) 件",
    "反証により棄却: \(.refuted | length) 件",
    "未検証のため保留: \(.unverified | length) 件\n",
    (if (.inline_comments | length) > 0 then
      "### 投稿予定\n" + ([.inline_comments[] | "- `\(.path):\(.line)` [\(.severity)] \(.body | split("\n")[0])"] | join("\n")) + "\n"
     else "" end),
    (if (.out_of_scope | length) > 0 then
      (if .issue_policy == "create" then "### Follow Up Issue 予定\n"
       else "### Issue 切り出し提案（このPRでは投稿・作成しない。ユーザー判断待ち）\n" end)
      + ([.out_of_scope[] | "- [\(.severity)] \(.title)"] | join("\n")) + "\n"
     else "" end)
  ' "$RUN_DIR/plans.json"
} >"$RUN_DIR/plan.md"

log "集約: $RUN_DIR/plans.json"
printf '%s\n' "$RUN_DIR"
