#!/usr/bin/env bash
# post.sh — collect.sh が作った草案を GitHub に反映する。
#
# 使い方:
#   post.sh <RUN_DIR> [--pr N]... [--confirmed]
#
# --confirmed を付けない限り書き込みを行わず、投稿予定を表示するだけで終わる。
# ユーザー承認は呼び出し側（Skill の手順）で取る。ここは最後の防壁として働く。
#
# out_of_scope の扱いは各 PR の plan.json に記録された issue_policy
# (collect.sh の --issue-policy) に従う。create なら Follow Up Issue を
# 自動作成し、suggest なら作成せず提案として表示するだけにする。
# post.sh 側で改めて方針を指定する必要はない。

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLUGIN_ROOT="${CLAUDE_PLUGIN_ROOT:-$(cd "$SCRIPT_DIR/../.." && pwd)}"
# shellcheck source=../herdr-fanout/lib/flow.sh
source "${HERDR_FANOUT_LIB:-$PLUGIN_ROOT/skills/herdr-fanout/lib/flow.sh}"
# shellcheck source=../gh-review-guard/lib/review-guard.sh
source "${GH_REVIEW_GUARD_LIB:-$PLUGIN_ROOT/skills/gh-review-guard/lib/review-guard.sh}"

RUN_DIR=""
CONFIRMED=0
ONLY_PRS=()

while [ $# -gt 0 ]; do
  case "$1" in
    --pr) ONLY_PRS+=("$2"); shift 2 ;;
    --confirmed) CONFIRMED=1; shift ;;
    -h|--help) sed -n '2,15p' "$0"; exit 0 ;;
    -*) flow_die "不明なオプション: $1" ;;
    *) RUN_DIR="$1"; shift ;;
  esac
done

command -v gh >/dev/null || flow_die "gh が PATH にない"
command -v jq >/dev/null || flow_die "jq が PATH にない"
[ -n "$RUN_DIR" ] && [ -f "$RUN_DIR/plans.json" ] || flow_die "plans.json のある RUN_DIR を指定する"

REPO=$(jq -r '.repo' "$RUN_DIR/plans.json")
[ -n "$REPO" ] && [ "$REPO" != "null" ] || flow_die "plans.json から repo を読めない"

total_comments=0
total_issues=0
total_suggestions=0
total_dropped=0

mapfile -t PR_LIST < <(jq -r '.plans[].pr' "$RUN_DIR/plans.json")

for pr in "${PR_LIST[@]}"; do
  if [ "${#ONLY_PRS[@]}" -gt 0 ]; then
    printf '%s\n' "${ONLY_PRS[@]}" | grep -qx "$pr" || continue
  fi

  phase "#$pr"
  plan=$(jq --argjson pr "$pr" '.plans[] | select(.pr == $pr)' "$RUN_DIR/plans.json")
  issue_policy=$(printf '%s' "$plan" | jq -r '.issue_policy // "suggest"')

  # 行番号の検証と重複除去は gh-review-guard に委譲する。
  # 既存コメントは投稿の直前に取得する。別のエージェントが
  # 先に書き込んでいる可能性があるため、事前取得を使い回さない。
  valid=$(guard_valid_lines "$REPO" "$pr")
  keys_file="$RUN_DIR/pr-$pr/existing-keys.txt"
  mkdir -p "$(dirname "$keys_file")"
  guard_existing_keys "$REPO" "$pr" >"$keys_file" 2>/dev/null || : >"$keys_file"

  filtered=$(guard_annotate "$(printf '%s' "$plan" | jq '.inline_comments')" "$valid" "$keys_file")

  postable=$(printf '%s' "$filtered" | jq '[.[] | select(.line_ok and (.dup | not))]')
  dropped=$(printf '%s' "$filtered" | jq '[.[] | select((.line_ok | not) or .dup)]')
  n_post=$(printf '%s' "$postable" | jq 'length')
  n_drop=$(printf '%s' "$dropped" | jq 'length')

  printf '%s' "$dropped" | jq -r '.[] | "  除外 \(.path):\(.line) 理由=\(if (.line_ok|not) then "行番号が差分に存在しない" else "同じ箇所にすでに自分がコメント済み" end)"' >&2

  # レビュー本文。suggestion ブロックは本文に入れず、インラインコメント側にだけ含める。
  # out_of_scope の指摘は本文には書かない。issue_policy に応じて別途扱う。
  body=$(jq -rn --argjson plan "$plan" --argjson posting "$postable" '
    "## 適正な実装\n\n"
    + (if ($plan.good_points | length) > 0
       then ($plan.good_points | map("- " + .) | join("\n"))
       else "- 特記なし" end)
    + "\n\n## 修正することが望ましいところ\n\n"
    + (if ($posting | length) > 0
       then ($posting | map("- `\(.path):\(.line)` [\(.severity)] " + (.body | split("\n")[0])) | join("\n"))
       else "- 敵対的検証を通過した指摘はありません" end)
    + "\n\n---\n\n対象スコープ: " + $plan.scope_summary
    + "\n\n本レビューは指摘ごとに反証を試みる検証を通したうえで、残ったものだけを記載しています。"
    + (if ($plan.refuted | length) > 0 then "\n反証により取り下げた候補: \($plan.refuted | length) 件。" else "" end)
    + (if ($plan.unverified | length) > 0 then "\n検証未完了のため保留した候補: \($plan.unverified | length) 件。" else "" end)
  ')

  n_out=$(printf '%s' "$plan" | jq '.out_of_scope | length')

  # 投稿するインラインコメントが 0 件なら、指摘なし = Approve 相当として扱う。
  # GitHub は comments 付きの APPROVE イベントを拒否するため、この分岐は排他にする。
  review_event="COMMENT"
  [ "$n_post" -eq 0 ] && review_event="APPROVE"

  if [ "$CONFIRMED" != "1" ]; then
    printf '\n--- dry-run: 投稿しない ---\n' >&2
    printf 'イベント: %s\n' "$review_event" >&2
    printf 'インラインコメント %s 件 / 除外 %s 件 / out_of_scope %s 件 (issue_policy=%s)\n' "$n_post" "$n_drop" "$n_out" "$issue_policy" >&2
    printf '\n[review body]\n%s\n' "$body" >&2
    printf '%s' "$postable" | jq -r '.[] | "\n[inline] \(.path):\(.line)\n\(.body)"' >&2
    if [ "$issue_policy" = "create" ]; then
      printf '%s' "$plan" | jq -r '.out_of_scope[] | "\n[issue] \(.title)\n\(.body)"' >&2
    else
      printf '%s' "$plan" | jq -r '.out_of_scope[] | "\n[issue 提案・未作成] \(.title)\n\(.body)"' >&2
    fi
    total_comments=$((total_comments + n_post))
    total_dropped=$((total_dropped + n_drop))
    if [ "$issue_policy" = "create" ]; then total_issues=$((total_issues + n_out)); else total_suggestions=$((total_suggestions + n_out)); fi
    continue
  fi

  # レビュー投稿
  if guard_post_review "$REPO" "$pr" "$body" "$postable" "$review_event"; then
    log "#$pr: レビューを投稿した (イベント=$review_event / コメント $n_post 件)"
    total_comments=$((total_comments + n_post))
  else
    log "#$pr: レビュー投稿に失敗した"
  fi

  # out_of_scope の扱い。issue_policy=create のときだけ Follow Up Issue を自動作成する。
  # suggest のときは作成せず、提案としてログに出すだけにとどめる。
  if [ "$issue_policy" = "create" ]; then
    while IFS= read -r issue; do
      [ -n "$issue" ] || continue
      title=$(printf '%s' "$issue" | jq -r '.title')
      ibody=$(printf '%s' "$issue" | jq -r '.body')
      url=$(gh issue create --repo "$REPO" --title "$title" \
        --body "$ibody

---
PR #$pr のレビュー中に発見。当該 PR のスコープ外と判断したため別 Issue にしています。" 2>/dev/null) || {
        log "#$pr: Issue 作成に失敗: $title"
        continue
      }
      log "#$pr: Issue 作成 $url"
      total_issues=$((total_issues + 1))
    done < <(printf '%s' "$plan" | jq -c '.out_of_scope[]')
  else
    n_suggest_shown=0
    while IFS= read -r sug; do
      [ -n "$sug" ] || continue
      title=$(printf '%s' "$sug" | jq -r '.title')
      log "#$pr: Issue 切り出し提案（未作成）: $title"
      n_suggest_shown=$((n_suggest_shown + 1))
    done < <(printf '%s' "$plan" | jq -c '.out_of_scope[]')
    total_suggestions=$((total_suggestions + n_suggest_shown))
  fi

  total_dropped=$((total_dropped + n_drop))
done

phase "完了"
if [ "$CONFIRMED" = "1" ]; then
  log "投稿したコメント $total_comments 件 / 作成した Issue $total_issues 件 / Issue 切り出し提案(未作成) $total_suggestions 件 / 除外 $total_dropped 件"
  if [ "$total_suggestions" -gt 0 ]; then
    log "Issue 切り出し提案の詳細は plan.md か plans.json の out_of_scope を確認し、必要なら gh issue create で個別に作成する"
  fi
else
  log "dry-run。投稿予定コメント $total_comments 件 / 作成予定 Issue $total_issues 件 / 提案のみ $total_suggestions 件 / 除外 $total_dropped 件"
  log "実際に投稿するには --confirmed を付けて再実行する"
fi
