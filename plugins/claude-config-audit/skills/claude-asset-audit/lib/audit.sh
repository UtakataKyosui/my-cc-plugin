#!/usr/bin/env bash
# Claude 資産(Skills / Rules / SubAgents / Hooks / Commands / OutputStyles)を
# Opus 5 / Sonnet 5 のプロンプト指針に照らして機械的に検査する関数群。
#
#   source ${CLAUDE_PLUGIN_ROOT}/skills/claude-asset-audit/lib/audit.sh
#   audit_all | audit_report
#
# 各検査は "severity<TAB>check<TAB>location<TAB>message" の行を出力する。
# severity は ERROR / WARN / INFO の3段階。

AUDIT_ROOT="${AUDIT_ROOT:-$HOME/.claude}"

# plugins/ は plugin 管理下で編集できないため既定の走査対象に含めない。
AUDIT_DIRS="${AUDIT_DIRS:-rules skills agents hooks commands output-styles}"

# 走査から外すパス。既定でこのスキル自身を外す。禁止パターンの文字列を
# 網羅的に列挙しているため、走査するとレポートが自己言及だけで埋まる。
AUDIT_EXCLUDE_RE="${AUDIT_EXCLUDE_RE:-/skills/claude-asset-audit/}"

_audit_emit() { printf '%s\t%s\t%s\t%s\n' "$1" "$2" "$3" "$4"; }

# 走査対象の Markdown を列挙する。
_audit_files_raw() {
  local d
  for d in $AUDIT_DIRS; do
    [ -d "$AUDIT_ROOT/$d" ] || continue
    # hooks は .sh しか無いが、注意文をモデルの文脈へ注入する以上、
    # 中の日本語はルール本文と同じくプロンプト面である。
    find "$AUDIT_ROOT/$d" -type f \( -name '*.md' -o -name '*.sh' \) 2>/dev/null
  done
  [ -f "$AUDIT_ROOT/CLAUDE.md" ] && printf '%s\n' "$AUDIT_ROOT/CLAUDE.md"
  return 0
}

audit_files() {
  _audit_files_raw | grep -vE "$AUDIT_EXCLUDE_RE"
  return 0
}

audit_relpath() { printf '%s\n' "${1#"$AUDIT_ROOT"/}"; }

# フロントマターから単一キーの値を取り出す。
_audit_fm() {
  awk -v key="$2" '
    NR==1 && $0 == "---" { inside=1; next }
    inside && $0 == "---" { exit }
    inside && !collect && index($0, key ":") == 1 {
      sub("^" key ":[ \t]*", "")
      # ブロックスカラー(| や >)と空値は後続のインデント行が本体になる
      if ($0 == "|" || $0 == ">" || $0 == "|-" || $0 == ">-" || $0 == "") { collect=1; next }
      print; exit
    }
    collect {
      if ($0 ~ /^[ \t]+[^ \t]/) { line=$0; sub(/^[ \t]+/, "", line); buf = (buf == "" ? line : buf " " line); next }
      exit
    }
    END { if (buf != "") print buf }
  ' "$1"
}

_audit_fm_has_key() {
  awk -v key="$2" '
    NR==1 && $0 == "---" { inside=1; next }
    inside && $0 == "---" { exit }
    inside && index($0, key ":") == 1 { found=1; exit }
    END { exit(found ? 0 : 1) }
  ' "$1"
}

# --- 決定的な手順の行を除外するためのガード -------------------------------
# 「lint を実行してからコミット」のような決定的ツール手順は Opus 5 でも残す。
# 除去すべきなのはモデル自身の再確認だけなので、コマンドや CI を含む行は落とす。
_AUDIT_TOOL_LINE_RE='`|\bjj\b|\bgit\b|\bgh\b|pnpm|npm |npx|lint|Lint|linter|formatter|フォーマット|test|Test|テスト|\bCI\b|push|commit|コミット|スクリプト|hook|フック'

_audit_scan() {
  local sev="$1" check="$2" re="$3" msg="$4" f hit line text
  audit_files | while IFS= read -r f; do
    while IFS= read -r hit; do
      line="${hit%%:*}"
      text="${hit#*:}"
      case "$check" in
        self-recheck|final-verification-step)
          printf '%s' "$text" | grep -qE "$_AUDIT_TOOL_LINE_RE" && continue
          ;;
        subagent-verification)
          # 「検証用の worktree」のように、検証がモデルの再確認を指さない用法を落とす
          printf '%s' "$text" | grep -qE '検証用|worktree|workspace' && continue
          ;;
      esac
      _audit_emit "$sev" "$check" "$(audit_relpath "$f"):$line" "$msg / $(printf '%s' "$text" | cut -c1-110)"
    done < <(grep -nE "$re" "$f" 2>/dev/null)
  done
}

# --- 検査1: モデル自身に再確認を指示していないか ---------------------------
# Opus 5 は指示なしで自己修正するため、再確認の指示は費用だけ増やす。
audit_self_recheck() {
  _audit_scan WARN self-recheck \
    'ダブルチェック|念のため[^。]{0,12}(確認|見直|検証)|(回答|返答|報告|出力)[^。]{0,12}前に[^。]{0,12}(再確認|再検証|自己検証|見直)|double-?check|re-?verify|verify (your|its) (own )?(work|answer|output|result)|sanity-?check your' \
    'モデル自身への再確認指示の疑い(Opus 5 は既定で自己修正する)'
}

# --- 検査2: 検証専用ステップを別途設けていないか ---------------------------
audit_final_verification_step() {
  _audit_scan WARN final-verification-step \
    '最終(的な)?(検証|確認)(ステップ|フェーズ|工程)|検証(ステップ|フェーズ)を(設け|追加|挟)|final verification step|verification step for any' \
    '独立した検証ステップの指示(Opus 5 では過剰検証を招く)'
}

# --- 検査3: サブエージェントに自分の作業の検証をさせていないか -------------
audit_subagent_verification() {
  _audit_scan INFO subagent-verification \
    '(サブエージェント|subagent|Agent ツール)[^。]{0,60}(検証|反証|ダブルチェック|verify|double-?check)|(検証|反証|verify|double-?check)[^。]{0,60}(サブエージェント|subagent|Agent ツール)' \
    'サブエージェントによる検証(Opus 5 の指針と衝突しうる。意図的な二段構えかを判断する)'
}

# --- 検査4: レビュー指示に重要度フィルタを埋め込んでいないか ---------------
# Sonnet 5 / Opus 5 はこの指示を literal に守り、recall が落ちる。
audit_severity_filter() {
  _audit_scan WARN severity-filter \
    '(重大|重要|高深刻度|高重要度|critical|high-severity)[^。]{0,24}(のみ|だけ|only)|only report high|be conservative|重箱の隅|軽微な[^。]{0,12}(指摘|問題)[^。]{0,12}(除外|省略|報告しない)' \
    'レビュー段階での重要度フィルタ(発見と絞り込みは段を分ける)'
}

# --- 検査5: SubAgent フロントマターの黙って壊れる書き方 --------------------
audit_agent_frontmatter() {
  local f rel tools
  [ -d "$AUDIT_ROOT/agents" ] || return 0
  for f in "$AUDIT_ROOT"/agents/*.md; do
    [ -f "$f" ] || continue
    rel="$(audit_relpath "$f")"

    if _audit_fm_has_key "$f" disallowed-tools; then
      _audit_emit ERROR frontmatter-key "$rel" \
        'disallowed-tools は未知キーとして無視される。disallowedTools に直す'
    fi

    if _audit_fm_has_key "$f" skills; then
      tools="$(_audit_fm "$f" tools)"
      case "$tools" in
        *Skill*) : ;;
        *) _audit_emit ERROR skills-preload "$rel" \
             'skills: があるが tools: に Skill がない。プリロードが黙って無効になる' ;;
      esac
    fi

    _audit_fm_has_key "$f" model || _audit_emit WARN model-unset "$rel" \
      'model: 未指定。セッションのモデルをそのまま継承する'

    if _audit_fm_has_key "$f" effort; then
      _audit_emit INFO effort-sweep "$rel" \
        "effort: $(_audit_fm "$f" effort) — Opus 5 では low/medium が主要な費用レバー。実測で再掃引する"
    fi
  done
}

# --- 検査6: Skill フロントマターの整合性 -----------------------------------
audit_skill_frontmatter() {
  local f rel dir name desc len
  [ -d "$AUDIT_ROOT/skills" ] || return 0
  for f in "$AUDIT_ROOT"/skills/*/SKILL.md; do
    [ -f "$f" ] || continue
    rel="$(audit_relpath "$f")"
    dir="$(basename "$(dirname "$f")")"
    name="$(_audit_fm "$f" name)"
    desc="$(_audit_fm "$f" description)"

    if [ -z "$name" ]; then
      _audit_emit ERROR skill-name "$rel" 'name: が無い'
    elif [ "$name" != "$dir" ]; then
      _audit_emit ERROR skill-name "$rel" "name: '$name' がディレクトリ名 '$dir' と一致しない"
    fi

    if [ -z "$desc" ]; then
      _audit_emit ERROR skill-description "$rel" \
        'description: が無い。モデルは description だけで起動を判断するため必須'
    else
      len=${#desc}
      if [ "$len" -gt 1024 ]; then
        _audit_emit ERROR skill-description "$rel" "description が ${len} 文字。上限 1024 を超えている"
      elif [ "$len" -lt 40 ]; then
        _audit_emit WARN skill-description "$rel" \
          "description が ${len} 文字。いつ使うかが書かれておらず起動判断ができない"
      fi
    fi

    case "$(_audit_fm "$f" disable-model-invocation)" in
      true)
        _audit_emit INFO disable-model-invocation "$rel" \
          '安全担保に使っているなら hook 層へ移す(rules/agent-skill-architecture.md)' ;;
    esac
  done
}

# --- 検査7: プリロード不能な組み合わせ -------------------------------------
audit_preload_conflicts() {
  local a rel s
  [ -d "$AUDIT_ROOT/agents" ] || return 0
  for a in "$AUDIT_ROOT"/agents/*.md; do
    [ -f "$a" ] || continue
    rel="$(audit_relpath "$a")"
    while IFS= read -r s; do
      [ -n "$s" ] || continue
      if [ ! -f "$AUDIT_ROOT/skills/$s/SKILL.md" ]; then
        _audit_emit ERROR skills-preload "$rel" "skills: の '$s' がユーザーレベルに存在しない"
      elif [ "$(_audit_fm "$AUDIT_ROOT/skills/$s/SKILL.md" disable-model-invocation)" = "true" ]; then
        _audit_emit ERROR skills-preload "$rel" \
          "skills: の '$s' は disable-model-invocation: true でプリロードできない"
      fi
    done < <(awk '
      NR==1 && $0 == "---" { inside=1; next }
      inside && $0 == "---" { exit }
      inside && $0 == "skills:" { list=1; next }
      inside && list && $0 ~ /^  *- / { sub(/^  *- */, ""); print; next }
      inside && list && $0 !~ /^  / { list=0 }
    ' "$a")
  done
}

# --- 検査8: 冗長さの制御が明示されているか ---------------------------------
# Opus 5 は既定の応答も書き出す文書も前世代より長い。長さの明示がなければ伸びる。
audit_verbosity_control() {
  local hits
  hits="$(audit_files | xargs grep -lE '簡潔|concise|冗長|verbosity|長さを(合わせ|そろえ)|filler' 2>/dev/null | wc -l | tr -d ' ')"
  if [ "$hits" = "0" ]; then
    _audit_emit WARN verbosity-control "(全体)" \
      '応答と成果物の長さを明示している資産が1つも無い。Opus 5 では既定で伸びる'
  else
    _audit_emit INFO verbosity-control "(全体)" \
      "長さに言及する資産 ${hits} 件。書き出す文書の長さ校正も入っているか確認する"
  fi
}

# --- 検査9: 委譲の上限が定義されているか -----------------------------------
audit_delegation_cap() {
  local hits
  hits="$(audit_files | xargs grep -lE 'MAX_SUBAGENT_SPAWN_DEPTH|MAX_CONCURRENT_SUBAGENTS|委譲(しない|の上限)|サブエージェントを?(乱用|増やさ)' 2>/dev/null | wc -l | tr -d ' ')"
  [ "$hits" = "0" ] && _audit_emit WARN delegation-cap "(全体)" \
    'サブエージェント委譲の上限に触れた資産が無い。Opus 5 は委譲しやすく費用が増える'
  return 0
}

# --- 検査10: agent-routing のロール定義 ------------------------------------
audit_routing_roles() {
  local json="$AUDIT_ROOT/skills/agent-routing/data/roles.json"
  [ -f "$json" ] || return 0
  command -v jq >/dev/null 2>&1 || {
    _audit_emit INFO routing-roles "skills/agent-routing/data/roles.json" 'jq が無いため未検査'
    return 0
  }
  local role model effort
  while IFS=$'\t' read -r role model effort; do
    [ -n "$role" ] || continue
    _audit_emit INFO effort-sweep "skills/agent-routing/data/roles.json" \
      "ロール $role = $model / $effort — Opus 5 の effort 掃引をやり直す対象"
    case "$role" in
      refute|verify|verifier)
        _audit_emit INFO subagent-verification "skills/agent-routing/data/roles.json" \
          "ロール $role はサブエージェントに検証を担わせる設計。rules/agent-routing.md と agents/role-verifier.md も併せて判断する" ;;
    esac
  done < <(jq -r 'to_entries[] | [.key, .value.model, .value.effort] | @tsv' "$json")
}

audit_all() {
  audit_agent_frontmatter
  audit_skill_frontmatter
  audit_preload_conflicts
  audit_self_recheck
  audit_final_verification_step
  audit_subagent_verification
  audit_severity_filter
  audit_verbosity_control
  audit_delegation_cap
  audit_routing_roles
}

# 検査結果(標準入力)を Markdown の表にする。
audit_report() {
  local tmp; tmp="$(mktemp)"
  sort -t"$(printf '\t')" -k1,1 -k2,2 > "$tmp"
  printf '## 検査結果\n\n'
  printf '| 重大度 | 検査 | 場所 | 内容 |\n|---|---|---|---|\n'
  awk -F'\t' '{ gsub(/\|/, "\\|"); printf "| %s | %s | `%s` | %s |\n", $1, $2, $3, $4 }' "$tmp"
  printf '\n合計 %s 件 (ERROR %s / WARN %s / INFO %s)\n' \
    "$(wc -l < "$tmp" | tr -d ' ')" \
    "$(grep -c '^ERROR' "$tmp" || true)" \
    "$(grep -c '^WARN' "$tmp" || true)" \
    "$(grep -c '^INFO' "$tmp" || true)"
  rm -f "$tmp"
}
