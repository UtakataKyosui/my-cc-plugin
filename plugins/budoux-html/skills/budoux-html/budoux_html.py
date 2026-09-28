#!/usr/bin/env python3
"""HTML ファイルの日本語テキストに BudouX の文節境界で <wbr> を入れ、改行用の CSS を注入する。

使い方: python budoux_html.py <file.html> [<file.html> ...]
ファイルを上書きする。何度実行しても結果は同じ（既存の <wbr> を外してから入れ直す）。
"""
import html
import re
import sys

import budoux

SKIP_TAGS = {"style", "script", "code", "pre", "title", "textarea", "svg"}
CJK = re.compile(r"[぀-ヿ㐀-鿿！-｠]")
TAG = re.compile(r"(<[^>]+>)")
TAG_NAME = re.compile(r"<\s*(/?)\s*([a-zA-Z0-9]+)")
CSS_MARKER = "/* budoux-html */"
CSS = (
    f"{CSS_MARKER}\n"
    "  body { word-break: keep-all; overflow-wrap: break-word; line-break: strict; }\n"
)
# ja-slop-guard の BudouxHtml MCP が入れる同等の指定。残すと body の指定が二重になる
MCP_CSS = re.compile(r"/\* ja-slop-guard: budoux \*/\s*body\s*\{[^}]*\}\s*")


def segment(text: str, parser) -> str:
    if not CJK.search(text):
        return text
    chunks = parser.parse(html.unescape(text))
    return "<wbr>".join(html.escape(c, quote=False) for c in chunks)


def process(src: str, parser) -> str:
    src = re.sub(r"<wbr\s*/?>", "", src)
    out, skip_depth = [], 0
    for part in TAG.split(src):
        if part.startswith("<") and part.endswith(">"):
            m = TAG_NAME.match(part)
            if m and m.group(2).lower() in SKIP_TAGS and not part.endswith("/>"):
                skip_depth += -1 if m.group(1) else 1
                skip_depth = max(skip_depth, 0)
            out.append(part)
        elif skip_depth or not part.strip():
            out.append(part)
        else:
            out.append(segment(part, parser))
    result = MCP_CSS.sub("", "".join(out))
    if CSS_MARKER not in result and "</style>" in result:
        result = result.replace("</style>", "  " + CSS + "</style>", 1)
    return result


def main(paths: list[str]) -> None:
    parser = budoux.load_default_japanese_parser()
    for path in paths:
        with open(path, encoding="utf-8") as f:
            src = f.read()
        dst = process(src, parser)
        with open(path, "w", encoding="utf-8") as f:
            f.write(dst)
        print(f"{path}: {dst.count('<wbr>')} <wbr>")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
