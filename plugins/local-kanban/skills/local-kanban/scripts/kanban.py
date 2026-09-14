#!/usr/bin/env python3
"""Local Kanban Board - file-based kanban manager stored in .kanban/board.json"""

import json
import os
import re
import sys
import argparse
from datetime import datetime

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x1f\x7f]")

BOARD_FILE = os.path.join(".kanban", "board.json")
COLUMNS = ["todo", "in-progress", "done"]
PRIORITIES = ["low", "medium", "high"]


def load_board():
    if not os.path.exists(BOARD_FILE):
        return {"issues": []}
    with open(BOARD_FILE, encoding="utf-8") as f:
        return json.load(f)


def save_board(board):
    os.makedirs(".kanban", exist_ok=True)
    with open(BOARD_FILE, "w", encoding="utf-8") as f:
        json.dump(board, f, indent=2, ensure_ascii=False)


def get_next_id(board):
    if not board["issues"]:
        return 1
    return max(i["id"] for i in board["issues"]) + 1


def hyperlink(url, text):
    """OSC 8 terminal hyperlink: clickable in iTerm2, Warp, kitty, etc.

    url/text に ESC などの制御文字が混じっていると OSC 8 シーケンスを途中で
    終端させ、端末へ任意の制御シーケンスを注入できてしまう。他リポジトリの
    ボードを取り込んだ場合など信頼できない入力もあるため、制御文字を含む
    場合はハイパーリンクを諦め、text 側からも制御文字を除いたプレーン
    テキストを返す。text をそのまま返すと、フォールバック経路自体が
    インジェクションを素通しにしてしまう。
    """
    if _CONTROL_CHAR_RE.search(url) or _CONTROL_CHAR_RE.search(text):
        return _CONTROL_CHAR_RE.sub("", text)
    return f"\033]8;;{url}\033\\{text}\033]8;;\033\\"


def format_title(issue):
    """タイトルを URL があればクリッカブルリンクとして返す"""
    title = issue["title"]
    url = issue.get("url", "")
    if url:
        return hyperlink(url, title)
    return _CONTROL_CHAR_RE.sub("", title)


def output(data, as_json=False):
    if as_json:
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif isinstance(data, str):
        print(data)
    elif isinstance(data, list):
        for item in data:
            print(item)


def cmd_init(args):
    if os.path.exists(BOARD_FILE):
        output("Board already exists.", args.json)
        return
    save_board({"issues": []})
    output(f"Board initialized at {BOARD_FILE}", args.json)


def cmd_add(args):
    board = load_board()
    issue_id = get_next_id(board)
    issue = {
        "id": issue_id,
        "title": args.title,
        "description": args.description or "",
        "priority": args.priority or "medium",
        "column": "todo",
        "labels": args.labels or [],
        "url": args.url or "",
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
    }
    board["issues"].append(issue)
    save_board(board)
    if args.json:
        output(issue, as_json=True)
    else:
        print(f"Added issue #{issue_id}: {args.title}")


def cmd_list(args):
    board = load_board()
    issues = board["issues"]
    if args.column:
        issues = [i for i in issues if i["column"] == args.column]
    if args.json:
        output(issues, as_json=True)
        return
    if not issues:
        print("No issues found.")
        return
    for issue in issues:
        labels = f" [{', '.join(issue.get('labels', []))}]" if issue.get("labels") else ""
        title = format_title(issue)
        print(f"#{issue['id']} [{issue['column']}] ({issue['priority']}) {title}{labels}")


def cmd_board(args):
    board = load_board()
    if args.json:
        grouped = {col: [i for i in board["issues"] if i["column"] == col] for col in COLUMNS}
        output(grouped, as_json=True)
        return
    for col in COLUMNS:
        issues = [i for i in board["issues"] if i["column"] == col]
        print(f"\n=== {col.upper()} ({len(issues)}) ===")
        for issue in issues:
            labels = f" [{', '.join(issue.get('labels', []))}]" if issue.get("labels") else ""
            title = format_title(issue)
            print(f"  #{issue['id']} ({issue['priority']}) {title}{labels}")


def cmd_show(args):
    board = load_board()
    issue = next((i for i in board["issues"] if i["id"] == args.id), None)
    if not issue:
        print(f"Issue #{args.id} not found.", file=sys.stderr)
        sys.exit(1)
    if args.json:
        output(issue, as_json=True)
        return
    labels = f"\nLabels: {', '.join(issue['labels'])}" if issue.get("labels") else ""
    desc = f"\nDescription:\n  {issue['description']}" if issue["description"] else ""
    url_line = f"\nURL: {hyperlink(issue['url'], issue['url'])}" if issue.get("url") else ""
    print(
        f"#{issue['id']} {issue['title']}\n"
        f"Column: {issue['column']}  Priority: {issue['priority']}{labels}{url_line}{desc}\n"
        f"Created: {issue['created_at']}"
    )


def cmd_move(args):
    board = load_board()
    issue = next((i for i in board["issues"] if i["id"] == args.id), None)
    if not issue:
        print(f"Issue #{args.id} not found.", file=sys.stderr)
        sys.exit(1)
    old_col = issue["column"]
    issue["column"] = args.column
    issue["updated_at"] = datetime.now().isoformat()
    save_board(board)
    if args.json:
        output(issue, as_json=True)
    else:
        print(f"Moved #{args.id} from {old_col} to {args.column}")


def cmd_update(args):
    board = load_board()
    issue = next((i for i in board["issues"] if i["id"] == args.id), None)
    if not issue:
        print(f"Issue #{args.id} not found.", file=sys.stderr)
        sys.exit(1)
    if args.title is not None:
        issue["title"] = args.title
    if args.description is not None:
        issue["description"] = args.description
    if args.priority is not None:
        issue["priority"] = args.priority
    if args.labels is not None:
        issue["labels"] = args.labels
    if args.url is not None:
        issue["url"] = args.url
    issue["updated_at"] = datetime.now().isoformat()
    save_board(board)
    if args.json:
        output(issue, as_json=True)
    else:
        print(f"Updated issue #{args.id}")


def cmd_delete(args):
    board = load_board()
    issue = next((i for i in board["issues"] if i["id"] == args.id), None)
    if not issue:
        print(f"Issue #{args.id} not found.", file=sys.stderr)
        sys.exit(1)
    board["issues"] = [i for i in board["issues"] if i["id"] != args.id]
    save_board(board)
    if args.json:
        output({"deleted": args.id}, as_json=True)
    else:
        print(f"Deleted issue #{args.id}")


def main():
    parser = argparse.ArgumentParser(description="Local Kanban Board")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    sub = parser.add_subparsers(dest="command")

    # --json はルートパーサーだけでなく各サブコマンドにも登録する。argparse は
    # サブコマンド名の後ろに続くオプションをサブパーサー側でしか解決できないため、
    # ルート専用のままだと `kanban.py board --json` のような、ドキュメントが
    # 案内する「どのコマンドの後にも --json を付けられる」呼び出しが
    # "unrecognized arguments" で失敗する。
    # サブコマンド側の default は argparse.SUPPRESS にする。store_true のまま
    # default=False にすると、`kanban.py --json board`(先頭指定)のようにルートで
    # --json を立てても、サブパーサーの解析時に指定なしのデフォルト False で
    # namespace が上書きされてしまう。SUPPRESS は「指定されなければ何もセット
    # しない」ため、ルート側でセットした True がサブパーサー解析後も残る。

    p = sub.add_parser("init", help="Initialize a new board")
    p.add_argument(
        "--json", action="store_true", default=argparse.SUPPRESS, help="Output as JSON"
    )

    p = sub.add_parser("add", help="Add a new issue")
    p.add_argument("--title", "-t", required=True)
    p.add_argument("--description", "-d", default="")
    p.add_argument("--priority", "-p", choices=PRIORITIES, default="medium")
    p.add_argument("--labels", "-l", nargs="*")
    p.add_argument("--url", "-u", default="")
    p.add_argument(
        "--json", action="store_true", default=argparse.SUPPRESS, help="Output as JSON"
    )

    p = sub.add_parser("list", help="List issues")
    p.add_argument("--column", "-c", choices=COLUMNS)
    p.add_argument(
        "--json", action="store_true", default=argparse.SUPPRESS, help="Output as JSON"
    )

    p = sub.add_parser("board", help="Show full board")
    p.add_argument(
        "--json", action="store_true", default=argparse.SUPPRESS, help="Output as JSON"
    )

    p = sub.add_parser("show", help="Show issue details")
    p.add_argument("id", type=int)
    p.add_argument(
        "--json", action="store_true", default=argparse.SUPPRESS, help="Output as JSON"
    )

    p = sub.add_parser("move", help="Move issue to column")
    p.add_argument("id", type=int)
    p.add_argument("column", choices=COLUMNS)
    p.add_argument(
        "--json", action="store_true", default=argparse.SUPPRESS, help="Output as JSON"
    )

    p = sub.add_parser("update", help="Update an issue")
    p.add_argument("id", type=int)
    p.add_argument("--title", "-t")
    p.add_argument("--description", "-d")
    p.add_argument("--priority", "-p", choices=PRIORITIES)
    p.add_argument("--labels", "-l", nargs="*")
    p.add_argument("--url", "-u")
    p.add_argument(
        "--json", action="store_true", default=argparse.SUPPRESS, help="Output as JSON"
    )

    p = sub.add_parser("delete", help="Delete an issue")
    p.add_argument("id", type=int)
    p.add_argument(
        "--json", action="store_true", default=argparse.SUPPRESS, help="Output as JSON"
    )

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return

    cmds = {
        "init": cmd_init,
        "add": cmd_add,
        "list": cmd_list,
        "board": cmd_board,
        "show": cmd_show,
        "move": cmd_move,
        "update": cmd_update,
        "delete": cmd_delete,
    }
    cmds[args.command](args)


if __name__ == "__main__":
    main()
