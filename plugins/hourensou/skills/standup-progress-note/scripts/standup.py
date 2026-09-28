#!/usr/bin/env python3
"""定例の進捗報告テキストの雛形を作り、検査し、クリップボードへ入れる。

サブコマンド:
  new      雛形を標準出力へ出す
  validate 検査する。違反があれば終了コード 1
  copy     検査を通ってから pbcopy する
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

MAX_BULLET_CHARS = 100
MAX_WORKSTREAM_CHARS = 300
MAX_TOTAL_CHARS = 800
MIN_BULLETS = 3
MAX_BULLETS = 5

CONFIRM_PREFIX = "確認したいこと:"
# 「まで」単独は「レビュー依頼まで出しました」のような完了の記述に当たるため入れない。
DEADLINE_TOKEN = re.compile(r"今日中|明日|明後日|今週|来週|\d{1,2}/\d{1,2}|までに")
HEADER = re.compile(r"^\d{1,2}/\d{1,2}\s+\S")
# 行全体で禁止する記号。PR 番号の # は行頭のみ禁止するため、ここには入れない。
INLINE_MARKDOWN = re.compile(r"[*`|]")
LEADING_MARKDOWN = re.compile(r"^\s*(#|\||\*|\+|\d+\.)\s")


@dataclass
class Workstream:
    name: str
    line_no: int
    bullets: list[tuple[int, str]] = field(default_factory=list)

    @property
    def body_chars(self) -> int:
        return sum(len(text) for _, text in self.bullets)


@dataclass
class Finding:
    rule: str
    where: str
    message: str

    def render(self) -> str:
        return f"  {self.rule:<18} {self.where}: {self.message}"


def parse(text: str) -> tuple[list[str], list[Workstream]]:
    """ヘッダ行とワークストリームに分ける。文字数は len() で数える（バイト数ではない）。"""
    lines = text.rstrip("\n").split("\n")
    workstreams: list[Workstream] = []
    current: Workstream | None = None
    # ヘッダの次の行から見る。2 行目が空行でない崩れた形でも取りこぼさない。
    for i, line in enumerate(lines[1:], start=2):
        if not line.strip():
            current = None
            continue
        if line.lstrip().startswith("- "):
            if current is not None:
                current.bullets.append((i, line))
            continue
        current = Workstream(name=line.strip(), line_no=i)
        workstreams.append(current)
    return lines, workstreams


def validate(text: str, limits: argparse.Namespace) -> tuple[list[Finding], list[Finding]]:
    lines, workstreams = parse(text)
    violations: list[Finding] = []
    warnings: list[Finding] = []

    if not lines or not HEADER.match(lines[0]):
        violations.append(Finding("header-date", "L1", "1 行目を「9/17 内部定例」の形にする"))
    if len(lines) < 2 or lines[1].strip():
        violations.append(Finding("header-blank", "L2", "2 行目は空行にする"))

    if not workstreams:
        violations.append(Finding("no-workstream", "全体", "ワークストリームが 1 つもない"))

    for i, line in enumerate(lines, start=1):
        if line != line.rstrip():
            violations.append(Finding("trailing-space", f"L{i}", "行末の空白を削る"))
        if "\r" in line:
            violations.append(Finding("crlf", f"L{i}", "改行コードを LF にする"))
        if INLINE_MARKDOWN.search(line):
            violations.append(
                Finding("no-markdown", f"L{i}", "* と ` と | は使わない。読み上げと Slack で崩れる")
            )
        if LEADING_MARKDOWN.match(line):
            violations.append(
                Finding("no-markdown", f"L{i}", "箇条書きの記号はハイフン 1 つにする")
            )

    for ws in workstreams:
        n = len(ws.bullets)
        if n < limits.min_bullets or n > limits.max_bullets:
            violations.append(
                Finding(
                    "bullet-count",
                    ws.name,
                    f"箇条書きが {n} 個。{limits.min_bullets}〜{limits.max_bullets} 個にする",
                )
            )
        if ws.body_chars > limits.max_workstream_chars:
            violations.append(
                Finding(
                    "workstream-chars",
                    ws.name,
                    f"{ws.body_chars} 文字。{limits.max_workstream_chars} 文字以内にする",
                )
            )
        for line_no, bullet in ws.bullets:
            if len(bullet) > limits.max_bullet_chars:
                violations.append(
                    Finding(
                        "bullet-chars",
                        f"L{line_no}",
                        f"{len(bullet)} 文字。{limits.max_bullet_chars} 文字以内にする",
                    )
                )

        if not any(DEADLINE_TOKEN.search(b) for _, b in ws.bullets):
            violations.append(
                Finding("deadline", ws.name, "いつまでにやるかが 1 行も書かれていない")
            )

        confirms = [(no, b) for no, b in ws.bullets if CONFIRM_PREFIX in b]
        if len(confirms) > 1:
            violations.append(
                Finding("confirm-once", ws.name, f"「{CONFIRM_PREFIX}」の行が {len(confirms)} 個ある")
            )
        if confirms and ws.bullets and confirms[-1][0] != ws.bullets[-1][0]:
            violations.append(
                Finding("confirm-last", ws.name, f"「{CONFIRM_PREFIX}」は最後の箇条書きにする")
            )

    total = len(text)
    if total > limits.max_total_chars:
        warnings.append(
            Finding("total-chars", "全体", f"{total} 文字。{limits.max_total_chars} 文字が目安")
        )

    return violations, warnings


def cmd_new(args: argparse.Namespace) -> int:
    names = list(args.workstream)
    if args.from_file:
        _, previous = parse(Path(args.from_file).read_text(encoding="utf-8"))
        names = [ws.name for ws in previous] + names
    if not names:
        print("ワークストリーム名を --workstream か --from で渡す", file=sys.stderr)
        return 2

    out = [f"{args.date} {args.meeting}", ""]
    for name in names:
        out += [
            name,
            "- <前回の報告以降に終わったこと。前回「今日中にやる」と言ったことの結果を含める>",
            "- <次に何をするか>。<いつまでにやるか>",
            f"- {CONFIRM_PREFIX} <その場にいる人に判断を仰ぎたいこと。なければこの行ごと消す>",
            "",
        ]
    print("\n".join(out).rstrip() + "\n", end="")
    return 0


def report(path: str, violations: list[Finding], warnings: list[Finding]) -> None:
    for finding in warnings:
        print(f"WARN {finding.render().strip()}", file=sys.stderr)
    if violations:
        print(f"NG {path}", file=sys.stderr)
        for finding in violations:
            print(finding.render(), file=sys.stderr)


def cmd_validate(args: argparse.Namespace) -> int:
    text = Path(args.file).read_text(encoding="utf-8")
    violations, warnings = validate(text, args)
    report(args.file, violations, warnings)
    if violations:
        return 1
    print(f"OK {args.file} ({len(text)} 文字)")
    return 0


def cmd_copy(args: argparse.Namespace) -> int:
    text = Path(args.file).read_text(encoding="utf-8")
    violations, warnings = validate(text, args)
    report(args.file, violations, warnings)
    if violations:
        print("検査を通っていないためコピーしていない", file=sys.stderr)
        return 1
    subprocess.run(["pbcopy"], input=text.encode("utf-8"), check=True)
    print(f"OK {args.file} ({len(text)} 文字) をクリップボードへ入れた")
    return 0


def add_limits(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--max-bullet-chars", type=int, default=MAX_BULLET_CHARS, dest="max_bullet_chars")
    parser.add_argument("--max-workstream-chars", type=int, default=MAX_WORKSTREAM_CHARS, dest="max_workstream_chars")
    parser.add_argument("--max-total-chars", type=int, default=MAX_TOTAL_CHARS, dest="max_total_chars")
    parser.add_argument("--min-bullets", type=int, default=MIN_BULLETS, dest="min_bullets")
    parser.add_argument("--max-bullets", type=int, default=MAX_BULLETS, dest="max_bullets")


def main() -> int:
    parser = argparse.ArgumentParser(prog="standup.py", description=__doc__)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_new = sub.add_parser("new", help="雛形を出す")
    p_new.add_argument("--date", required=True, help="例: 9/17")
    p_new.add_argument("--meeting", default="内部定例")
    p_new.add_argument("--workstream", action="append", default=[])
    p_new.add_argument("--from", dest="from_file", help="前回のファイルからワークストリーム名を引き継ぐ")
    p_new.set_defaults(func=cmd_new)

    p_validate = sub.add_parser("validate", help="検査する")
    p_validate.add_argument("file")
    add_limits(p_validate)
    p_validate.set_defaults(func=cmd_validate)

    p_copy = sub.add_parser("copy", help="検査してから pbcopy する")
    p_copy.add_argument("file")
    add_limits(p_copy)
    p_copy.set_defaults(func=cmd_copy)

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
