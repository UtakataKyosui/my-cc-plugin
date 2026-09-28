#!/usr/bin/env bash
# UserPromptSubmit hook: cwd が junct の案件配下のとき、その案件で見積もり消化率が
# 閾値を超えている未完タスクを検知して注意を注入する。junct DB は読み取り専用で開き、
# 報連相ドラフトの作成はメインエージェントの判断に委ねる（~/.claude/rules/deadline-hourensou.md）。
# 失敗時は何も出力せず exit 0 する（プロンプト送信をブロックしない）。

set -u

DB="$HOME/Library/Application Support/com.taikiamo.junct/junct.sqlite3"
STATE="${CLAUDE_PLUGIN_ROOT:-$HOME/.claude/plugins/hourensou}/.deadline-alert-state"
COOLDOWN_SECONDS=3600  # 同じタスクへの注意は 1 時間に 1 回だけ
THRESHOLD_PERCENT=70   # 見積もり消化率がこの値以上で注意する

[ -f "$DB" ] || exit 0
command -v sqlite3 > /dev/null 2>&1 || exit 0
command -v jq > /dev/null 2>&1 || exit 0

INPUT=$(cat)
CWD=$(printf '%s' "$INPUT" | jq -r '.cwd // empty' 2>/dev/null)
[ -n "$CWD" ] || exit 0

# スキーマが想定と違う junct バージョンでは何もしない
TASK_COLS=$(sqlite3 -readonly "$DB" "select group_concat(name) from pragma_table_info('task')" 2>/dev/null) || exit 0
case ",$TASK_COLS," in
  *,estimated_hours,*) ;;
  *) exit 0 ;;
esac
ENTRY_COLS=$(sqlite3 -readonly "$DB" "select group_concat(name) from pragma_table_info('task_time_entry')" 2>/dev/null) || exit 0
case ",$ENTRY_COLS," in
  *,started_at,*) ;;
  *) exit 0 ;;
esac

# active 案件の working_dir と cwd_aliases を列挙し、cwd の前方一致で案件を特定する
MATCH=$(sqlite3 -readonly -separator $'\t' "$DB" "
  select p.id, p.name, dir from (
    select id, name, working_dir as dir from project where status='active' and working_dir is not null
    union all
    select p2.id, p2.name, j.value as dir
    from project p2, json_each(p2.cwd_aliases) j
    where p2.status='active'
  ) as t
  join project p on p.id = t.id
" 2>/dev/null) || exit 0
[ -n "$MATCH" ] || exit 0

PROJECT_ID=""
PROJECT_NAME=""
while IFS=$'\t' read -r pid pname dir; do
  case "$dir" in
    "~"*) dir="$HOME${dir#\~}" ;;
  esac
  [ -n "$dir" ] || continue
  case "$CWD" in
    "$dir"|"$dir"/*)
      PROJECT_ID="$pid"
      PROJECT_NAME="$pname"
      break
      ;;
  esac
done <<< "$MATCH"

[ -n "$PROJECT_ID" ] || exit 0

# 見積もりがあり未完のタスクについて、実績秒の合計から消化率を出す
RISKS=$(sqlite3 -readonly -separator $'\t' "$DB" "
  select t.id, t.title, t.estimated_hours,
    round(sum(strftime('%s', coalesce(e.ended_at, 'now')) - strftime('%s', e.started_at)) / 3600.0, 1) as spent_hours,
    cast(sum(strftime('%s', coalesce(e.ended_at, 'now')) - strftime('%s', e.started_at)) * 100.0
      / (t.estimated_hours * 3600.0) as integer) as percent
  from task t
  join task_time_entry e on e.task_id = t.id
  where t.project_id = $PROJECT_ID
    and t.estimated_hours is not null
    and t.estimated_hours > 0
    and (t.status is null or t.status not in ('completed', 'done', 'cancelled', 'archived'))
  group by t.id
  having percent >= $THRESHOLD_PERCENT
  order by percent desc
  limit 3
" 2>/dev/null) || exit 0
[ -n "$RISKS" ] || exit 0

# クールダウン: 同じタスクへの注意は一定時間に 1 回だけ
NOW=$(date +%s)
LINES=""
NEW_STATE=""
while IFS=$'\t' read -r tid title est spent percent; do
  [ -n "$tid" ] || continue
  LAST=$(grep "^$tid " "$STATE" 2>/dev/null | cut -d' ' -f2)
  if [ -n "$LAST" ] && [ $(( NOW - LAST )) -lt "$COOLDOWN_SECONDS" ]; then
    NEW_STATE="$NEW_STATE$tid $LAST
"
    continue
  fi
  NEW_STATE="$NEW_STATE$tid $NOW
"
  LINES="$LINES- タスク「${title}」(id: ${tid}): 見積もり ${est}h に対して実績 ${spent}h、消化率 ${percent}%
"
done <<< "$RISKS"
printf '%s' "$NEW_STATE" > "$STATE.tmp" && mv "$STATE.tmp" "$STATE"

[ -n "$LINES" ] || exit 0

CTX="[期限リスク] junct 案件「${PROJECT_NAME}」に見積もり消化率が ${THRESHOLD_PERCENT}% を超えた未完タスクがあります。
${LINES}該当タスクが未完なら遅延の可能性があるため、Skill hourensou:deadline-hourensou で報告・連絡のドラフト作成を提案してください。すでに完了しているなら complete_task の呼び忘れなので片付けてください（~/.claude/rules/deadline-hourensou.md）。"

jq -n --arg ctx "$CTX" '{hookSpecificOutput: {hookEventName: "UserPromptSubmit", additionalContext: $ctx}}'
exit 0
