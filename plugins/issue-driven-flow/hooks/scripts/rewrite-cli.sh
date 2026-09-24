#!/usr/bin/env bash
# PreToolUse hook: classic CLI コマンドを Rust 代替ツールへ自動リライト
#
# 動作:
#   - RUST_CLI_REWRITE=0 で全体無効化
#   - RUST_CLI_REWRITE_LIST でリライト対象コマンドを絞り込み（カンマ区切り）
#   - 代替ツール未インストール時はリライトせず元コマンドを通過（壊れない）
#   - RTK プレフィックス（rtk ls など）はリライト後も保持
#   - 既に Rust 代替ツールが指定されている場合はノータッチ

set -uo pipefail

# jq が必要（なければ通過）
command -v jq &>/dev/null || exit 0

# RUST_CLI_REWRITE=0 で無効化
[[ "${RUST_CLI_REWRITE:-1}" == "0" ]] && exit 0

INPUT=$(cat)
if ! CMD=$(jq -r '.tool_input.command // empty' 2>/dev/null <<<"$INPUT"); then
    exit 0
fi
[[ -z "$CMD" ]] && exit 0

# RTK プレフィックスを分離して保持
RTK_PREFIX=""
BARE_CMD="$CMD"
if [[ "$BARE_CMD" =~ ^rtk[[:space:]]+(.*)$ ]]; then
    RTK_PREFIX="rtk "
    BARE_CMD="${BASH_REMATCH[1]}"
fi

# 既に Rust 代替ツールが指定されている場合はスキップ
RUST_TOOLS="eza lsd fd broot tre rg bat sd hexyl btm procs dust delta gitui tokei hyperfine just watchexec xh miniserve starship atuin yazi jaq ouch"
FIRST_WORD="${BARE_CMD%% *}"
for tool in $RUST_TOOLS; do
    [[ "$FIRST_WORD" == "$tool" ]] && exit 0
done

# シェルメタ文字が含まれる場合は安全のためリライトをスキップ
# （例: "ls; date" の末尾にフラグが誤付与されるのを防ぐ）
# ; & | < > ! を変数経由で渡す（[[ =~ ]] に直書きすると ; & がシェル構文として解釈されるため）
_META_RE='[;&|<>!]'
if [[ "$BARE_CMD" =~ $_META_RE ]]; then
    exit 0
fi

# リライト対象リストをパース
IFS=',' read -ra REWRITE_LIST <<<"${RUST_CLI_REWRITE_LIST:-ls,cat,grep,du,ps,diff,hexdump,tree,jq,find}"

list_has() {
    local needle="$1"
    for entry in "${REWRITE_LIST[@]}"; do
        [[ "${entry// /}" == "$needle" ]] && return 0
    done
    return 1
}

NEW_CMD=""

# ls → eza --git --icons --group-directories-first
if list_has "ls" && command -v eza &>/dev/null; then
    if [[ "$BARE_CMD" == "ls" || "$BARE_CMD" =~ ^ls[[:space:]] ]]; then
        REWRITTEN="${BARE_CMD/#ls/eza}"
        NEW_CMD="$REWRITTEN --git --icons --group-directories-first"
    fi
fi

# cat <file> → bat --plain <file>
# 単一ファイル引数のみ対応（quoted path も許容）
# 正規表現を変数で定義（[[ =~ ]] に引用符を直書きすると解釈が壊れるため）
if [[ -z "$NEW_CMD" ]] && list_has "cat" && command -v bat &>/dev/null; then
    _cat_re_dq='^cat[[:space:]]+"[^"]+"$'
    _cat_re_sq="^cat[[:space:]]+'[^']+'$"
    _cat_re_uq='^cat[[:space:]]+[^[:space:]]+$'
    if [[ "$BARE_CMD" =~ $_cat_re_dq || "$BARE_CMD" =~ $_cat_re_sq || "$BARE_CMD" =~ $_cat_re_uq ]]; then
        NEW_CMD="${BARE_CMD/#cat/bat --plain}"
    fi
fi

# grep -r* → rg（-r フラグが含まれる場合のみ。rg はデフォルト再帰的なので -r を除去）
if [[ -z "$NEW_CMD" ]] && list_has "grep" && command -v rg &>/dev/null; then
    if [[ "$BARE_CMD" =~ ^grep[[:space:]] ]]; then
        REST="${BARE_CMD#grep }"
        if [[ "$REST" =~ (^|[[:space:]])-[a-zA-Z]*r ]]; then
            # フラグトークンのみ -r を除去する（パターン・パス文字列は変更しない）
            # word splitting は quoted string を壊すが、フラグ部分のみを対象にすることで
            # sed を全文字列に適用する旧実装のパターン誤変更問題を回避する
            NEW_REST=""
            HAS_R=0
            IN_FLAGS=1
            for word in $REST; do
                if [[ "$IN_FLAGS" -eq 1 && "$word" =~ ^- ]]; then
                    if [[ "$word" == "-r" ]]; then
                        HAS_R=1
                        continue
                    elif [[ "$word" =~ r ]]; then
                        HAS_R=1
                        word="${word//r/}"
                        [[ "$word" == "-" ]] && continue
                    fi
                else
                    IN_FLAGS=0
                fi
                NEW_REST="${NEW_REST:+$NEW_REST }$word"
            done
            [[ "$HAS_R" -eq 1 ]] && NEW_CMD="rg $NEW_REST"
        fi
    fi
fi

# du → dust
# dust は du のフラグ（-s/-h 等）を受け付けないため、フラグなし・パスのみの場合のみリライト
# migration cheatsheet: du -sh . → dust（フラグは引き継がない）
if [[ -z "$NEW_CMD" ]] && list_has "du" && command -v dust &>/dev/null; then
    if [[ "$BARE_CMD" == "du" ]]; then
        NEW_CMD="dust"
    elif [[ "$BARE_CMD" =~ ^du[[:space:]]+[^-] ]]; then
        NEW_CMD="${BARE_CMD/#du/dust}"
    fi
fi

# ps → procs
# procs は ps のフラグを解釈しないため、フラグなしの場合のみリライト
if [[ -z "$NEW_CMD" ]] && list_has "ps" && command -v procs &>/dev/null; then
    if [[ "$BARE_CMD" == "ps" ]]; then
        NEW_CMD="procs"
    fi
fi

# diff → delta
if [[ -z "$NEW_CMD" ]] && list_has "diff" && command -v delta &>/dev/null; then
    if [[ "$BARE_CMD" == "diff" || "$BARE_CMD" =~ ^diff[[:space:]] ]]; then
        NEW_CMD="${BARE_CMD/#diff/delta}"
    fi
fi

# hexdump → hexyl（-C フラグを除去：hexyl はデフォルトで canonical 表示）
if [[ -z "$NEW_CMD" ]] && list_has "hexdump" && command -v hexyl &>/dev/null; then
    if [[ "$BARE_CMD" == "hexdump" || "$BARE_CMD" =~ ^hexdump[[:space:]] ]]; then
        REST="${BARE_CMD#hexdump}"
        REST=$(echo "$REST" | sed -E 's/ -C( |$)/ /g' | tr -s ' ' | sed -E 's/^ +| +$//')
        NEW_CMD="hexyl${REST:+ $REST}"
    fi
fi

# tree → tre
if [[ -z "$NEW_CMD" ]] && list_has "tree" && command -v tre &>/dev/null; then
    if [[ "$BARE_CMD" == "tree" || "$BARE_CMD" =~ ^tree[[:space:]] ]]; then
        NEW_CMD="${BARE_CMD/#tree/tre}"
    fi
fi

# jq → jaq（jq 構文互換）
if [[ -z "$NEW_CMD" ]] && list_has "jq" && command -v jaq &>/dev/null; then
    if [[ "$BARE_CMD" == "jq" || "$BARE_CMD" =~ ^jq[[:space:]] ]]; then
        NEW_CMD="${BARE_CMD/#jq/jaq}"
    fi
fi

# find → fd（安全にリライトできる単純パターンのみ）
# -exec/-mtime/-size/-maxdepth など複雑な述語は通過
if [[ -z "$NEW_CMD" ]] && list_has "find" && command -v fd &>/dev/null; then
    if [[ "$BARE_CMD" == "find" || "$BARE_CMD" =~ ^find[[:space:]] ]]; then
        FIND_SKIP=0
        for _fp in -exec -mtime -atime -ctime -size -newer -empty -perm -user -group \
                   -delete -prune -printf -fprintf -maxdepth -mindepth; do
            # スペース囲みで完全一致判定（ファイル名との誤一致を防ぐ）
            [[ " $BARE_CMD " == *" $_fp "* ]] && { FIND_SKIP=1; break; }
        done
        [[ "$BARE_CMD" =~ [[:space:]](-not|-or[[:space:]]|-and[[:space:]]|\\\() ]] && FIND_SKIP=1

        if [[ "$FIND_SKIP" -eq 0 ]]; then
            FIND_REST="${BARE_CMD#find}"
            FIND_REST="${FIND_REST#"${FIND_REST%%[![:space:]]*}"}"
            FIND_PATH="."
            FIND_NAME=""
            FIND_TYPE=""
            FIND_OK=1

            while [[ -n "$FIND_REST" && "$FIND_OK" -eq 1 ]]; do
                FIND_REST="${FIND_REST#"${FIND_REST%%[![:space:]]*}"}"
                [[ -z "$FIND_REST" ]] && break
                # クォート付き・スペース含みパターンも正しく解釈するためグループ化
                if [[ "$FIND_REST" =~ ^-name[[:space:]]+(\'([^\']*)\'|\"([^\"]*)\"|([^[:space:]]+))(.*) ]]; then
                    if [[ -n "${BASH_REMATCH[2]}" ]]; then
                        FIND_RAW="${BASH_REMATCH[2]}"
                    elif [[ -n "${BASH_REMATCH[3]}" ]]; then
                        FIND_RAW="${BASH_REMATCH[3]}"
                    else
                        FIND_RAW="${BASH_REMATCH[4]}"
                    fi
                    FIND_REST="${BASH_REMATCH[5]}"
                    # 残存クォートがあればパース失敗扱い
                    [[ "$FIND_RAW" == *"'"* || "$FIND_RAW" == *'"'* ]] && { FIND_OK=0; break; }
                    FIND_NAME="$FIND_RAW"
                elif [[ "$FIND_REST" =~ ^-type[[:space:]]+([fd])(.*) ]]; then
                    FIND_TYPE="${BASH_REMATCH[1]}"
                    FIND_REST="${BASH_REMATCH[2]}"
                elif [[ "$FIND_REST" =~ ^-[a-zA-Z]+ ]]; then
                    FIND_OK=0
                elif [[ "$FIND_REST" =~ ^([^[:space:]]+)(.*) ]]; then
                    # 複数パス指定（例: find dir1 dir2 -name ...）は安全のため通過
                    if [[ "$FIND_PATH" != "." ]]; then
                        FIND_OK=0
                    else
                        FIND_PATH="${BASH_REMATCH[1]}"
                        FIND_REST="${BASH_REMATCH[2]}"
                    fi
                else
                    break
                fi
            done

            if [[ "$FIND_OK" -eq 1 && -n "$FIND_NAME" ]]; then
                FD_TYPE_ARG="${FIND_TYPE:+-t $FIND_TYPE }"

                if [[ "$FIND_NAME" =~ ^[*][.]([^.*?/]+)$ ]]; then
                    FD_PAT_ARG="-e ${BASH_REMATCH[1]}"
                elif [[ "$FIND_NAME" != *"*"* && "$FIND_NAME" != *"?"* && "$FIND_NAME" != *"["* ]]; then
                    # find -name は basename 完全一致。fd -g で glob 扱いにして等価性を維持
                    FD_PAT_ARG="-g $FIND_NAME"
                else
                    FIND_OK=0
                fi

                if [[ "$FIND_OK" -eq 1 ]]; then
                    if [[ "$FIND_PATH" == "." ]]; then
                        NEW_CMD="fd ${FD_TYPE_ARG}${FD_PAT_ARG}"
                    else
                        NEW_CMD="fd ${FD_TYPE_ARG}${FD_PAT_ARG} $FIND_PATH"
                    fi
                    NEW_CMD="${NEW_CMD//  / }"
                    NEW_CMD="${NEW_CMD% }"
                fi
            fi
        fi
    fi
fi

# リライトなし → 通過
[[ -z "$NEW_CMD" ]] && exit 0

# RTK プレフィックスを復元して tool_input.command のみ差し替える
# updatedInput は permissionDecision が allow のときだけ適用される
FINAL_CMD="${RTK_PREFIX}${NEW_CMD}"
jq --arg cmd "$FINAL_CMD" '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "allow",
    updatedInput: (.tool_input | .command = $cmd)
  }
}' <<<"$INPUT"
