#!/usr/bin/env bash
# collect.sh — 複数 PR に対する敵対的レビューを herdr のペイン上で並列実行し、
# 投稿予定の草案を作るところまでを行う。GitHub への書き込みは一切しない。
#
# 使い方:
#   collect.sh [PR番号...] [-R owner/repo] [--kind claude] [-j N] [--keep-panes]
#              [--discover args|review-requested] [--issue-policy create|suggest]
#
# PR 番号を渡すと --discover args と同じ扱いになる。省略すると
# --discover review-requested と同じ扱いになり、自分宛のレビュー依頼 PR
# (ドラフト除く)を gh wheel task -r -> gh my-task -> gh search の順に
# フォールバックして収集する。
#
# --issue-policy はスコープ外の指摘をどう扱うかを決め、plans.json に
# issue_policy として記録する。post.sh はこの値を読んで、Follow Up Issue を
# 自動作成する(create)か、切り出し案として表示するだけにする(suggest)かを
# 決める。post.sh 側で改めて指定する必要はない。
#
# 構造は Dynamic Workflow の pipeline() と同じ。PR ごとに
#   Review -> Verify -> Plan
# を独立に流すため、PR A の検証中に PR B のレビューが走る。段階間の barrier はない。
#
# review と refute のモデル・effort・ツール権限は skills/agent-routing の
# ロール定義を使う。ロールごとに個別の AGENT_ARGS を組み立てていた旧実装
# (review-requested-adversarial 由来)は廃止した。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
# shellcheck source=../herdr-fanout/lib/flow.sh
source "${HERDR_FANOUT_LIB:-$PLUGIN_ROOT/skills/herdr-fanout/lib/flow.sh}"
# shellcheck source=../agent-routing/lib/routing.sh
source "${AGENT_ROUTING_LIB:-$PLUGIN_ROOT/skills/agent-routing/lib/routing.sh}"

REPO=""
KIND="claude"
MAX_PARALLEL=3
DISCOVER=""
ISSUE_POLICY="suggest"
PRS=()
export FLOW_KEEP_PANES=0

while [ $# -gt 0 ]; do
  case "$1" in
    -R|--repo) REPO="$2"; shift 2 ;;
    --kind) KIND="$2"; shift 2 ;;
    -j|--jobs) MAX_PARALLEL="$2"; shift 2 ;;
    --keep-panes) FLOW_KEEP_PANES=1; shift ;;
    --discover) DISCOVER="$2"; shift 2 ;;
    --issue-policy) ISSUE_POLICY="$2"; shift 2 ;;
    -h|--help) sed -n '2,24p' "$0"; exit 0 ;;
    -*) flow_die "不明なオプション: $1" ;;
    *) PRS+=("$1"); shift ;;
  esac
done

case "$ISSUE_POLICY" in
  create|suggest) ;;
  *) flow_die "--issue-policy は create か suggest のみ受け付ける: $ISSUE_POLICY" ;;
esac

if [ -z "$DISCOVER" ]; then
  if [ "${#PRS[@]}" -gt 0 ]; then DISCOVER="args"; else DISCOVER="review-requested"; fi
fi
case "$DISCOVER" in
  args)
    [ "${#PRS[@]}" -gt 0 ] || flow_die "--discover args には PR 番号を1つ以上渡す"
    ;;
  review-requested) ;;
  *) flow_die "--discover は args か review-requested のみ受け付ける: $DISCOVER" ;;
esac

flow_init

[ -n "$REPO" ] || REPO="$(gh repo view --json nameWithOwner -q .nameWithOwner)" \
  || flow_die "リポジトリを特定できない。-R owner/repo を指定する"

if [ "$DISCOVER" = "review-requested" ]; then
  if gh extension list 2>/dev/null | grep -qi 'gh-wheel'; then
    log "gh wheel task -r でレビュー依頼 PR を収集する"
    mapfile -t PRS < <(gh wheel task -r -j -R "$REPO" | jq -r '.prs[]? | select(.isDraft == false) | .number')
  elif gh extension list 2>/dev/null | grep -qi 'gh-my-task'; then
    log "gh my-task でレビュー依頼 PR を収集する"
    mapfile -t PRS < <(gh my-task -r -j -R "$REPO" | jq -r '.prs[]? | select(.isDraft == false) | .number')
  else
    log "gh wheel / gh my-task が見つからないため gh search で代替収集する"
    mapfile -t PRS < <(gh search prs --repo "$REPO" --review-requested "@me" --state open --draft=false --json number \
      | jq -r '.[].number')
  fi
  [ "${#PRS[@]}" -gt 0 ] || flow_die "レビュー依頼されている PR が見つからない"
fi

RUN_DIR="${PRAR_OUT_DIR:-$HOME/.cache/pr-adversarial-review}/${REPO//\//_}/$FLOW_RUN_ID"
mkdir -p "$RUN_DIR"
export FLOW_TAB_LOG="$RUN_DIR/tabs.txt"
: >"$FLOW_TAB_LOG"
TIMING_FILE="$RUN_DIR/timing.jsonl"
: >"$TIMING_FILE"

trap flow_cleanup EXIT

log "リポジトリ: $REPO"
log "収集方法: $DISCOVER"
log "対象 PR: ${PRS[*]}"
log "Issue 方針: $ISSUE_POLICY"
log "出力先: $RUN_DIR"
log "並列数: $MAX_PARALLEL"

render_prompt() {
  local template="$1" pr="$2" findings="$3" verdicts="$4"
  sed -e "s|__REPO__|$REPO|g" \
      -e "s|__PR__|$pr|g" \
      -e "s|__FINDINGS__|$findings|g" \
      -e "s|__VERDICTS__|$verdicts|g" \
      "$SCRIPT_DIR/prompts/$template"
}

# 1 PR 分のパイプライン。サブシェルで並列に走る。
run_pr_pipeline() {
  local pr="$1"
  local dir="$RUN_DIR/pr-$pr"
  local findings="$dir/findings.json"
  local verdicts="$dir/verdicts.json"
  mkdir -p "$dir"

  # --- Review ---
  local rev="rev-$pr-$FLOW_RUN_ID"
  local pane t0 t1
  pane=$(flow_spawn "review #$pr" "$PWD") || return 1
  t0=$(date +%s)
  flow_agent_start_role "$rev" review "$pane" "$KIND" || {
    log "#$pr: レビュワーの起動に失敗"
    return 1
  }
  render_prompt reviewer.md "$pr" "$findings" "$verdicts" >"$dir/reviewer-prompt.txt"
  flow_agent_kick_role "$rev" "$dir/reviewer-prompt.txt" review || true
  local state
  state=$(flow_agent_join "$rev" "${PRAR_TIMEOUT_MS:-1800000}" "$findings")
  t1=$(date +%s)
  flow_record_timing "$TIMING_FILE" review "$rev" "pr-$pr" "$t0" "$t1" "$state"
  log "#$pr: レビュー完了状態=$state"

  if [ ! -s "$findings" ] || ! jq -e '.findings' "$findings" >/dev/null 2>&1; then
    log "#$pr: findings.json が得られなかった。ペインの末尾を保存する"
    herdr agent read "$rev" --source recent-unwrapped --lines 200 >"$dir/reviewer-tail.txt" 2>/dev/null || true
    return 1
  fi

  local n
  n=$(jq '.findings | length' "$findings")
  log "#$pr: 指摘 $n 件"

  # --- Verify（敵対的検証）---
  # 指摘 1 件ごとにペインを立てるとターミナルが破綻するため、
  # PR ごとに 1 人の反証者へ指摘配列をまとめて渡す。
  if [ "$n" -gt 0 ]; then
    local ref="ref-$pr-$FLOW_RUN_ID"
    local pane2
    pane2=$(flow_spawn "refute #$pr" "$PWD") || return 1
    t0=$(date +%s)
    flow_agent_start_role "$ref" refute "$pane2" "$KIND" || {
      log "#$pr: 検証者の起動に失敗"
      return 1
    }
    render_prompt refuter.md "$pr" "$findings" "$verdicts" >"$dir/refuter-prompt.txt"
    flow_agent_kick_role "$ref" "$dir/refuter-prompt.txt" refute || true
    state=$(flow_agent_join "$ref" "${PRAR_TIMEOUT_MS:-1800000}" "$verdicts")
    t1=$(date +%s)
    flow_record_timing "$TIMING_FILE" refute "$ref" "pr-$pr" "$t0" "$t1" "$state"
    log "#$pr: 検証完了状態=$state"
    if [ ! -s "$verdicts" ] || ! jq -e '.verdicts' "$verdicts" >/dev/null 2>&1; then
      log "#$pr: verdicts.json が得られなかった。全件を未検証として扱い保留する"
      herdr agent read "$ref" --source recent-unwrapped --lines 200 >"$dir/refuter-tail.txt" 2>/dev/null || true
      printf '{"pr":%s,"verdicts":[]}\n' "$pr" >"$verdicts"
    fi
  else
    printf '{"pr":%s,"verdicts":[]}\n' "$pr" >"$verdicts"
  fi

  # --- Plan（起案）---
  # 検証を通過した指摘だけを、投稿用と out-of-scope 用に振り分ける。
  # verdict のない指摘は保留にして投稿しない。
  # $V は id をキーにしたマップに畳んでから引く。
  # 生成子 ($V[] | select(...)) as $vd のままだと、verdicts.json に同一 id が
  # 複数あったときに as が件数分ボディを評価し、finding が重複して
  # 同じ指摘を二重投稿してしまう。LLM 出力に一意性は期待できない。
  jq -n --slurpfile f "$findings" --slurpfile v "$verdicts" --arg issue_policy "$ISSUE_POLICY" '
    ($f[0]) as $F
    | ($v[0].verdicts // []) as $Vraw
    | ($Vraw | group_by(.id) | map(.[0]) | INDEX(.id)) as $V
    | ($F.findings // []) as $items
    | [ $items[]
        | . as $it
        | ($V[$it.id]) as $vd
        | $it + {
            verdict: $vd,
            effective_scope: ($vd.scope_override // $it.scope)
          }
      ] as $judged
    | {
        pr: $F.pr,
        pr_title: $F.pr_title,
        linked_issues: ($F.linked_issues // []),
        scope_summary: ($F.scope_summary // ""),
        good_points: ($F.good_points // []),
        issue_policy: $issue_policy,
        confirmed: [ $judged[] | select(.verdict.refuted == false) ],
        refuted:   [ $judged[] | select(.verdict.refuted == true) ],
        unverified: [ $items[] | select( $V[.id] == null ) ]
      }
    | . + {
        inline_comments: [
          .confirmed[]
          | select(.effective_scope == "in-scope")
          | select((.review_comment // "") != "")
          | select(.verdict.line_valid != false)
          | {path, line, severity, id, body: .review_comment}
        ],
        out_of_scope: [
          .confirmed[]
          | select(.effective_scope == "out-of-scope")
          | select((.issue_title // "") != "")
          | {id, title: .issue_title, body: .issue_body, severity, path, line}
        ]
      }
  ' >"$dir/plan.json"

  log "#$pr: 起案完了 -> $dir/plan.json"
}

# --- fan out（同時実行数を絞りながら投入する）---
phase "Review -> Verify -> Plan (${#PRS[@]} PR / 並列 $MAX_PARALLEL)"
pids=()
for pr in "${PRS[@]}"; do
  while [ "$(jobs -rp | wc -l | tr -d ' ')" -ge "$MAX_PARALLEL" ]; do
    perl -e 'select(undef,undef,undef,1)'
  done
  ( run_pr_pipeline "$pr" ) &
  pids+=("$!")
done
for p in "${pids[@]}"; do wait "$p" || true; done

# --- 集約 ---
phase "Summary"
export REPO FLOW_RUN_ID
jq -s '{
  repo: env.REPO,
  run_id: env.FLOW_RUN_ID,
  plans: .
}' "$RUN_DIR"/pr-*/plan.json >"$RUN_DIR/plans.json" 2>/dev/null \
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
      (if .issue_policy == "create"
       then "### Follow Up Issue 予定\n"
       else "### Issue 切り出し提案（このPRでは投稿・作成しない。ユーザー判断待ち）\n" end)
      + ([.out_of_scope[] | "- [\(.severity)] \(.title)"] | join("\n")) + "\n"
     else "" end)
  ' "$RUN_DIR/plans.json"
} >"$RUN_DIR/plan.md"

log "集約: $RUN_DIR/plans.json"
log "人が読む要約: $RUN_DIR/plan.md"
log "ロール別実測時間: $TIMING_FILE"
printf '%s\n' "$RUN_DIR"
