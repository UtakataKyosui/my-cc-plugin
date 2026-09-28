#!/usr/bin/env bash
# 機械的検査を実行して Markdown レポートを出す薄い入口。
# 判断が要る項目は references/checklist.md をモデルが読んで進める。
#
#   ./audit.sh                # 既定の走査対象
#   AUDIT_DIRS="rules" ./audit.sh
set -uo pipefail
source "${CLAUDE_ASSET_AUDIT_LIB:-$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/audit.sh}"

printf '# Claude 資産の棚卸し\n\n'
printf '走査対象: `%s` (AUDIT_ROOT=`%s`)\n\n' "$AUDIT_DIRS" "$AUDIT_ROOT"
audit_all | audit_report
