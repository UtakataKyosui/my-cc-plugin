#!/usr/bin/env bash
# flow.sh — Dynamic Workflow 相当のプリミティブを herdr CLI の上に実装する。
#
# 提供する関数:
#   flow_init                     実行 ID と出力ディレクトリを決める
#   phase <title>                 進捗ログを出す
#   log <msg>                     進捗ログを出す
#   flow_workspace_create <label> 専用のワークスペースを作り、以降の作成先にする
#   flow_spawn <label> <cwd>      タブを作り、シェルが使える状態になったペイン ID を返す
#   flow_agent_ask_instructions <dir>  ペイン側へ渡す質問の書き方を出力する
#   flow_agent_question <dir>     未回答の質問があれば中身を返す
#   flow_agent_answer <name> <dir> <text>  回答を書いてペイン側を再開させる
#   flow_agent_start <name> <kind> <pane> [-- args...]
#   flow_agent_kick <name> <prompt-file>
#   flow_agent_join <name> <timeout_ms> [artifact]
#   flow_agent_status <name>
#   flow_cleanup                  このスクリプトが作ったタブだけを閉じる
#
# 呼び出し側は set -euo pipefail を前提にしてよい。
#
# このファイルは source される前提のため、set や shopt で呼び出し側の
# シェルオプションを変更しない。source した対話シェルの挙動を書き換えるのは
# 副作用として過剰で、set -u を持ち込むと未定義変数の参照でシェルが落ちる。

# 作成したタブ ID はファイルに追記する。サブシェルで並列に spawn しても
# 親のクリーンアップから見えるようにするため、配列ではなくファイルを使う。
FLOW_TAB_LOG="${FLOW_TAB_LOG:-}"
FLOW_KEEP_PANES="${FLOW_KEEP_PANES:-0}"

# タブを作るワークスペース。既定は呼び出し元のワークスペースで、
# flow_workspace_create を呼ぶと専用のワークスペースへ切り替わる。
FLOW_WORKSPACE="${FLOW_WORKSPACE:-}"
# flow_workspace_create が作ったワークスペース。クリーンアップで閉じる対象を
# 自分が作ったものだけに限るため、渡されたものと作ったものを分けて持つ。
FLOW_OWN_WORKSPACE=""

flow_die() {
  printf '\033[31merror:\033[0m %s\n' "$*" >&2
  exit 1
}

log() { printf '\033[2m|\033[0m %s\n' "$*" >&2; }
phase() { printf '\n\033[1;36m== %s\033[0m\n' "$*" >&2; }

flow_init() {
  command -v herdr >/dev/null || flow_die "herdr が PATH にない"
  command -v jq >/dev/null || flow_die "jq が PATH にない"
  command -v gh >/dev/null || flow_die "gh が PATH にない"
  [ "${HERDR_ENV:-}" = "1" ] || flow_die "herdr のペイン内で実行していない (HERDR_ENV != 1)"

  FLOW_RUN_ID="${FLOW_RUN_ID:-$(date +%m%d%H%M)$(printf '%04x' $((RANDOM % 65536)))}"
  # agent 名は [a-z][a-z0-9_-]{0,31} に収める必要があるため run id を短く保つ
  FLOW_RUN_ID="$(printf '%s' "$FLOW_RUN_ID" | tr -cd 'a-z0-9' | cut -c1-12)"
  [ -n "$FLOW_RUN_ID" ] || FLOW_RUN_ID="r$$"
}

# ペインの前景がシェル 1 つだけになるまで待つ。
# tab create が返った直後は zprofile などが前景に残っており、
# agent start がそのまま失敗するため必ず経由する。
flow_wait_shell_ready() {
  local pane="$1" timeout_ms="${2:-15000}"
  local waited=0 step=250 n
  while [ "$waited" -lt "$timeout_ms" ]; do
    n=$(herdr pane process-info --pane "$pane" 2>/dev/null \
      | jq -r '.result.process_info.foreground_processes | length' 2>/dev/null || echo 99)
    if [ "$n" = "1" ]; then
      return 0
    fi
    perl -e "select(undef,undef,undef,$step/1000)"
    waited=$((waited + step))
  done
  return 1
}

# 新しいタブを作り、準備完了したルートペインの ID を stdout に返す。
# 1 タブ 1 エージェントにすることで、split の繰り返しによる極細ペインを避ける。
#
# 第3引数以降に --env KEY=VALUE を繰り返し渡すと、そのペインにだけ環境変数を
# 注入できる。CLAUDE_CODE_EFFORT_LEVEL のようにフロントマターより優先される
# 変数を使うとき、軽量経路(agents/*.md の effort:)とペイン経路で効き方を
# 揃えたい場合に使う。呼び出し側の既存コードは第3引数を渡さないので、
# このオプションを足しても既存の呼び出しは壊れない。
flow_spawn() {
  local label="$1" cwd="$2"
  shift 2
  local env_args=()
  while [ $# -gt 0 ]; do
    case "$1" in
      --env) env_args+=(--env "$2"); shift 2 ;;
      *) flow_die "flow_spawn: 不明な引数: $1" ;;
    esac
  done
  local out tab pane
  # --workspace を必ず渡す。省略すると UI でフォーカスされている
  # 他クライアントのワークスペースにタブが作られる。
  out=$(herdr tab create --workspace "${FLOW_WORKSPACE:-$HERDR_WORKSPACE_ID}" --cwd "$cwd" --label "$label" "${env_args[@]}" --no-focus) \
    || flow_die "tab create が失敗した ($label)"
  tab=$(printf '%s' "$out" | jq -r '.result.tab.tab_id')
  pane=$(printf '%s' "$out" | jq -r '.result.root_pane.pane_id')
  [ "$tab" != "null" ] && [ "$pane" != "null" ] || flow_die "tab create の応答から ID を読めない"
  [ -n "$FLOW_TAB_LOG" ] && printf '%s\n' "$tab" >>"$FLOW_TAB_LOG"
  flow_wait_shell_ready "$pane" 20000 || flow_die "$pane のシェルが準備完了にならなかった"
  printf '%s\n' "$pane"
}

# エージェントを起動する。tab 直後の競合に備えて数回リトライする。
flow_agent_start() {
  local name="$1" kind="$2" pane="$3"
  shift 3
  local attempt
  for attempt in 1 2 3; do
    if herdr agent start "$name" --kind "$kind" --pane "$pane" --timeout 60000 "$@" >/dev/null 2>&1; then
      log "起動: $name ($kind) -> $pane"
      # TUI が入力を受け付けるまでの猶予。これを置いても初回投入が
      # 落ちることはあるため、flow_agent_kick 側の再送と併用する。
      perl -e "select(undef,undef,undef,${FLOW_AGENT_GRACE_MS:-8000}/1000)"
      return 0
    fi
    log "起動リトライ $attempt/3: $name"
    flow_wait_shell_ready "$pane" 10000 || true
    perl -e 'select(undef,undef,undef,1.5)'
  done
  return 1
}

flow_agent_status() {
  herdr agent get "$1" 2>/dev/null | jq -r '.result.agent.agent_status // "unknown"'
}

# skills/agent-routing の route_args_into / route_grace_ms を使ってロール別に
# モデル・effort・ツール権限を組み立て、flow_agent_start へ委譲する。
# 呼び出し側が事前に skills/agent-routing/lib/routing.sh を source している
# ことを前提にする。この関数の中で source し直すと、run_pr_pipeline のような
# サブシェル内呼び出しで毎回読み直しになり無駄なので、あえてしない。
#
# kind を省略すると claude になる。
flow_agent_start_role() {
  local name="$1" role="$2" pane="$3" kind="${4:-claude}"
  command -v route_args_into >/dev/null 2>&1 \
    || flow_die "route_args_into が見つからない。呼び出し側で agent-routing/lib/routing.sh を source する"
  local args=()
  route_args_into args "$role"
  local grace
  grace=$(route_grace_ms "$role")
  # flow_agent_start は ${FLOW_AGENT_GRACE_MS:-8000} を直接参照する。ここで
  # local 変数として同名を再定義すると、bash の動的スコープにより
  # flow_agent_start 側もこの値を見る。グローバルを書き換えないので
  # 他ロールの起動と競合しない。
  local FLOW_AGENT_GRACE_MS="$grace"
  flow_agent_start "$name" "$kind" "$pane" -- "${args[@]}"
}

# flow_agent_kick をロール別の待ち時間(route_kick_ms)で呼ぶ。effort を
# 上げたロールほど初回応答が遅く、既定の待ち時間ではプロンプトが黙って
# 捨てられることがあるため、ロールごとに待ち時間を変える。
flow_agent_kick_role() {
  local name="$1" prompt_file="$2" role="$3"
  command -v route_kick_ms >/dev/null 2>&1 \
    || flow_die "route_kick_ms が見つからない。呼び出し側で agent-routing/lib/routing.sh を source する"
  local kick
  kick=$(route_kick_ms "$role")
  local FLOW_KICK_WAIT_MS="$kick"
  flow_agent_kick "$name" "$prompt_file"
}

# プロンプトを投げ、実際に working に入ったことを確認するまで待つ。投入は再試行する。
#
# なぜ再試行が必要か。agent start は herdr がエージェントを検出した時点で返るが、
# Claude Code の TUI はまだ入力を受け付けられる状態になっていない。
# MCP サーバーが多い環境では起動に数秒かかり、その間に送ったプロンプトは
# エラーにならず黙って捨てられる。agent prompt は成功を返し、
# interactive_ready も true のまま、入力欄は空という状態になる。
# 実測では 2 回目の投入で確実に届いた。
#
# --wait を付けずに投げてすぐ join すると、まだ idle の相手を完了と誤認するため、
# working への遷移を確認してから抜ける。
flow_agent_kick() {
  local name="$1" prompt_file="$2"
  local text attempt waited
  text=$(cat "$prompt_file")

  for attempt in 1 2 3; do
    herdr agent prompt "$name" "$text" >/dev/null 2>&1 || {
      log "投入コマンドが失敗: $name (試行 $attempt)"
      perl -e 'select(undef,undef,undef,2)'
      continue
    }
    waited=0
    while [ "$waited" -lt "${FLOW_KICK_WAIT_MS:-20000}" ]; do
      case "$(flow_agent_status "$name")" in
        working) log "投入: $name (試行 $attempt)"; return 0 ;;
        blocked) log "投入直後に blocked: $name"; return 0 ;;
        done) log "投入: $name (試行 $attempt, 即完了)"; return 0 ;;
      esac
      perl -e 'select(undef,undef,undef,0.5)'
      waited=$((waited + 500))
    done
    log "投入が届かなかったので再送する: $name (試行 $attempt)"
  done
  log "警告: $name にプロンプトを届けられなかった"
  return 1
}

# 完了まで待つ。戻り値は状態文字列。
#
# --until を省くと herdr は idle も settled とみなす。Claude Code はプロンプト
# 投入の直後とツール呼び出しの合間に idle へ落ちるため、省略すると投入直後の
# idle を拾って即座に返る。実測では投入から 2 秒後に idle、4 秒後に working、
# 8 秒後に done へ遷移した。この最初の idle で返ってしまい、レビュワーが
# 4 分 21 秒かけて書いた成果物を「得られなかった」と誤判定したことがある。
# done と blocked だけを待つ。
#
# artifact を渡すと、状態が確定したあとも成果物が現れるまで
# FLOW_ARTIFACT_GRACE_MS だけ待つ。done がファイルの書き込み完了よりわずかに
# 先に立つ場合に取りこぼさないための保険である。
flow_agent_join() {
  local name="$1" timeout_ms="${2:-900000}" artifact="${3:-}"
  herdr agent wait "$name" --until done --until blocked --timeout "$timeout_ms" >/dev/null 2>&1 || true
  if [ -n "$artifact" ] && [ ! -s "$artifact" ]; then
    local waited=0 grace="${FLOW_ARTIFACT_GRACE_MS:-60000}"
    while [ "$waited" -lt "$grace" ]; do
      perl -e 'select(undef,undef,undef,1)'
      waited=$((waited + 1000))
      [ -s "$artifact" ] && break
    done
  fi
  flow_agent_status "$name"
}

# ロール別の実測時間を1行の JSON として追記する。junct はレビュワーと検証者が
# 同一タスクへ合流するとフェーズを切り替えないため、この内訳は junct から
# 取れない。ここが唯一の取得元になる。
#
# 複数の PR が ( ) & のサブシェルで並列に走り、かつ同じ timing_file へ同時に
# 追記されるため、1レコードを1回の jq 呼び出しで組み立てて1行のまま
# >> で書く。複数の printf に分けて行を組み立てたり、複数行のブロックを
# 流し込んだりしない。行の途中で他プロセスの書き込みが混ざる余地を作らないためである。
flow_record_timing() {
  local timing_file="$1" role="$2" name="$3" target="$4" start_ts="$5" end_ts="$6" state="$7"
  [ -n "$timing_file" ] || return 0
  jq -nc \
    --arg role "$role" --arg name "$name" --arg target "$target" \
    --argjson started_at "$start_ts" --argjson ended_at "$end_ts" --arg state "$state" \
    '{role: $role, agent: $name, target: $target, started_at: $started_at, ended_at: $ended_at, duration_s: ($ended_at - $started_at), state: $state}' \
    >>"$timing_file"
}

# このスクリプトが作ったタブだけを閉じる。他セッションのタブには触れない。
# FLOW_TAB_LOG に自分で書いた ID しか対象にしないため、
# herdr tab list に出てくる他の作業を誤って閉じることがない。
# 専用のワークスペースを作り、以降の flow_spawn の作成先にする。
# 利用者の作業タブと混ざらないため、切り替えて中を見るのに一段深い操作が要る。
# --no-focus で作るので、作った時点では画面が切り替わらない。
#
# command substitution で呼ばないこと。サブシェルになり FLOW_WORKSPACE の代入が
# 親のシェルへ伝わらず、flow_spawn が呼び出し元のワークスペースへタブを作り続ける。
# 実測でこれを踏んだ。ID が要るときは呼んだあとに $FLOW_WORKSPACE を読む。
#
#   NG: WS=$(flow_workspace_create "label")
#   OK: flow_workspace_create "label" >/dev/null; WS="$FLOW_WORKSPACE"
flow_workspace_create() {
  local label="$1" out ws
  out=$(herdr workspace create --label "$label" --cwd "$PWD" --no-focus) \
    || flow_die "workspace create が失敗した ($label)"
  ws=$(printf '%s' "$out" | jq -r '.result.workspace.workspace_id')
  [ -n "$ws" ] && [ "$ws" != "null" ] || flow_die "workspace create の応答から ID を読めない"
  FLOW_WORKSPACE="$ws"
  FLOW_OWN_WORKSPACE="$ws"
  printf '%s\n' "$ws"
}

# --- ペイン側エージェントからの質問の中継 ---------------------------------
#
# ペイン側エージェントには AskUserQuestion を禁止してある。ペインで選択 UI を
# 出させてキーを送って答えさせる経路は、Claude Code が代替スクリーンで動くため
# 読み取りが不安定になる。かわりに次の手順で中継する。
#
#   1. ペイン側は <dir>/question.json を書き、その turn を終える
#   2. flow_agent_join が settled で返る
#   3. 呼び出し側が flow_agent_question で質問を取り出し、利用者に聞く
#   4. flow_agent_answer で回答を書き、herdr の prompt でペイン側を再開させる
#   5. 質問が無くなるまで 2 から繰り返す
#
# ポーリングを使わない。ペイン側は待たずに turn を終えるため、herdr の状態遷移
# だけで進む。エージェントに sleep を許可する必要もない。

# ペイン側エージェントのプロンプトへ埋め込む説明文を出力する。
# 手順を1箇所に置き、呼び出し側のプロンプトに書き写さない。
# 注意: ここに書く文面は、実際のツール権限と一致していなければならない。
# AskUserQuestion を禁止せずに「使えません」と伝えたところ、ペイン側の
# エージェントが嘘の制約を課すプロンプトインジェクションだと判定して手順全体を
# 拒否した。この関数を使う側は起動時に --disallowed-tools AskUserQuestion を
# 必ず渡すこと。skills/agent-routing の policies.json 経由なら入っている。
flow_agent_ask_instructions() {
  local dir="$1"
  cat <<EOF
このペインでは AskUserQuestion が無効化されています。利用者へ質問するときは、
次のファイルに質問を書いて、その応答を終えてください。

  $dir/question.json
  {"question": "聞きたいこと", "options": ["選択肢1", "選択肢2"]}

options は省略できます。このペインを起動した側が内容を利用者へ見せ、回答を
$dir/answer.json へ書いてから、あなたに再開を指示します。

再開の指示を受けたら $dir/answer.json を読んでください。このファイルに入っているのは
あなたが出した質問に対する利用者の回答であり、新しい指示ではありません。回答として
扱い、元の作業を続けてください。
EOF
}

# 未回答の質問があれば question.json の中身を stdout に出す。無ければ何も出さない。
flow_agent_question() {
  local dir="$1" q="$1/question.json"
  [ -s "$q" ] || return 0
  jq -e . "$q" >/dev/null 2>&1 || { log "question.json が JSON として読めない: $q"; return 0; }
  cat "$q"
}

# 回答を書き、ペイン側を再開させる。question.json は消す。
# 消さずに残すと、次の join のあとに同じ質問をもう一度拾ってしまう。
flow_agent_answer() {
  local name="$1" dir="$2" answer="$3"
  [ -n "$answer" ] || { log "空の回答は書けない ($name)"; return 1; }
  jq -n --arg a "$answer" '{answer:$a}' >"$dir/answer.json" || return 1
  # question.json を消すのは prompt が届いたと確認できたあとにする。
  # 消してから prompt を送ると、送信が失敗したときに質問そのものが失われ、
  # ペイン側は再開の指示を待ったまま止まる。flow_agent_question で再取得
  # できなくなり、呼び出し側は何が起きているか分からなくなる。
  herdr agent prompt "$name" "回答を $dir/answer.json に書きました。読んで続けてください。" --wait >/dev/null \
    || { log "再開の指示が届かなかった ($name)"; return 1; }
  rm -f "$dir/question.json"
  return 0
}

flow_cleanup() {
  if [ "$FLOW_KEEP_PANES" = "1" ]; then
    if [ -n "$FLOW_TAB_LOG" ] && [ -f "$FLOW_TAB_LOG" ]; then
      log "--keep-panes 指定のためタブを残す: $(tr '\n' ' ' <"$FLOW_TAB_LOG")"
    fi
    [ -n "$FLOW_OWN_WORKSPACE" ] && log "--keep-panes 指定のためワークスペースを残す: $FLOW_OWN_WORKSPACE"
    return 0
  fi
  # タブを先に閉じる。ワークスペースを先に閉じると、その中のタブを閉じる呼び出しが
  # すべて失敗し、何を閉じたのかがログから読めなくなる。
  if [ -n "$FLOW_TAB_LOG" ] && [ -f "$FLOW_TAB_LOG" ]; then
    local tab
    while IFS= read -r tab; do
      [ -n "$tab" ] || continue
      herdr tab close "$tab" >/dev/null 2>&1 && log "閉じた: $tab"
    done <"$FLOW_TAB_LOG"
  fi
  # 自分が作ったワークスペースだけを閉じる。呼び出し元から渡されたワークスペースや
  # 利用者の作業中のワークスペースには触れない。
  if [ -n "$FLOW_OWN_WORKSPACE" ]; then
    herdr workspace close "$FLOW_OWN_WORKSPACE" >/dev/null 2>&1 \
      && log "閉じた: $FLOW_OWN_WORKSPACE"
    FLOW_OWN_WORKSPACE=""
  fi
}
