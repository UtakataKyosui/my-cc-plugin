#!/usr/bin/env python3
"""clipboard-guard.py と standup.py の検査を確かめる。

  python3 test_guard.py

クリップボードへ流すコマンド名は分割して組み立てる。この定義自体を
clipboard-guard.py が実行位置の呼び出しと誤認しないようにするため。
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUARD = HERE / "clipboard-guard.py"
STANDUP = HERE / "standup.py"
SKILL_MD = HERE.parent / "SKILL.md"
COPY = "pb" + "copy"

VALID = """9/17 内部定例

開発ルールの整備
- PR #12 をマージし、公開と改訂が完了しました
- 残りの追随は、今日中にチケットを切ります
- 確認したいこと: この順で進めてよいか相談させてください
"""

INVALID = """2026-09-17 内部定例
開発ルールの整備
- **PR #12** をマージしました
"""


def guard(command: str) -> int:
    result = subprocess.run(
        [sys.executable, str(GUARD)],
        input=json.dumps({"tool_input": {"command": command}}),
        capture_output=True,
        text=True,
    )
    return result.returncode


def validate(path: Path) -> int:
    return subprocess.run(
        [sys.executable, str(STANDUP), "validate", str(path)],
        capture_output=True,
        text=True,
    ).returncode


def skill_md_example() -> str:
    """SKILL.md の最初のコードフェンスを取り出す。読み手が真似る見本そのものを検査する。"""
    body = SKILL_MD.read_text(encoding="utf-8")
    start = body.index("```", body.index("## 出力の形式"))
    start = body.index("\n", start) + 1
    end = body.index("```", start)
    return body[start:end]


def main() -> int:
    failures = 0
    with tempfile.TemporaryDirectory() as tmp:
        valid = Path(tmp) / "standup-valid.txt"
        invalid = Path(tmp) / "standup-invalid.txt"
        example = Path(tmp) / "standup-example.txt"
        valid.write_text(VALID, encoding="utf-8")
        invalid.write_text(INVALID, encoding="utf-8")
        example.write_text(skill_md_example(), encoding="utf-8")

        cases: list[tuple[str, int, int]] = [
            ("正規経路は通す", guard(f"python3 {STANDUP} copy {valid}"), 0),
            ("ガード自身のファイル名では止めない", guard(f"mv /tmp/a.py {GUARD} && echo standup"), 0),
            ("ヒアドキュメント直渡しは止める", guard(f"cat <<EOF | {COPY}\n9/17 内部定例\nstandup\nEOF"), 2),
            ("検査済みでも直接コピーは止める", guard(f"{COPY} < {valid}"), 2),
            ("検査に落ちるファイルは止める", guard(f"{COPY} < {invalid}"), 2),
            ("コメントに standup.py と書いても素通りさせない", guard(f"{COPY} < {invalid} ; echo standup.py"), 2),
            ("standup を含まないコピーは通す", guard(f"{COPY} < /tmp/memo.txt"), 0),
            ("無関係なコマンドは通す", guard("git status"), 0),
            ("正しい報告は検査を通る", validate(valid), 0),
            ("崩れた報告は検査に落ちる", validate(invalid), 1),
            ("SKILL.md の見本が検査を通る", validate(example), 0),
        ]

        for name, actual, expected in cases:
            if actual == expected:
                print(f"[PASS] {name}")
            else:
                failures += 1
                print(f"[FAIL] {name}: 終了コード {actual}（期待 {expected}）")

    print("\n全ケース通過" if not failures else f"\n{failures} 件失敗")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
