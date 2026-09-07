"""Markdown を意味検索用のチャンクに分割する。

見出し（H1-H6）単位でセクションに分け、各チャンクの先頭に
「ファイルタイトル > 見出しパンくず」を付与して文脈を補強する。
frontmatter を除去し、wiki リンクは意味語を残す形に正規化し、
各チャンクの開始行（1-based）を保持して file_path:line でジャンプできるようにする。
"""

from __future__ import annotations

import re
from pathlib import Path

_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_EMBED_RE = re.compile(r"!\[\[[^\]]*\]\]")
_ALIAS_LINK_RE = re.compile(r"\[\[([^\]|]+)\|([^\]]+)\]\]")
_PLAIN_LINK_RE = re.compile(r"\[\[([^\]]+)\]\]")

# パンくずに含める最大見出しレベル（H1-H3）。これより深い見出しは
# セクション境界にはなるがパンくずには積まない。
_MAX_BREADCRUMB_LEVEL = 3

# 1 チャンクあたりの最大文字数の既定値。既定モデル intfloat/multilingual-e5-small の
# 入力上限は 512 トークンで、超過分は SentenceTransformer が無言で切り捨てる。日本語は
# おおむね 1 文字 ≲ 1 トークンのため、パンくず・プレフィックス分の余裕を見て 480 文字に
# 収める（この値はパンくず連結後の「埋め込まれる実テキスト全体」の上限として扱う）。
_DEFAULT_MAX_CHARS = 480
_DEFAULT_OVERLAP = 96
# 予算が極端に小さくならないよう、piece に必ず確保する最低文字数。
_MIN_PIECE_CHARS = 80


def strip_frontmatter(text: str) -> tuple[str, int]:
    """先頭の YAML frontmatter を除去し、(本文, 除去行数) を返す。

    除去行数は、本文の行番号を元ファイルの行番号へ戻すためのオフセット。
    frontmatter が無ければ (元テキスト, 0)。
    """
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        return text, 0
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            removed = i + 1
            return "\n".join(lines[removed:]), removed
    # 閉じ `---` が無ければ frontmatter とみなさない
    return text, 0


def normalize_wikilinks(text: str) -> str:
    """wiki リンクを意味語に正規化する。

    - `![[embed]]`        → 除去（画像・埋め込みはノイズ）
    - `[[target|alias]]`  → alias
    - `[[target]]`        → target
    """
    text = _EMBED_RE.sub("", text)
    text = _ALIAS_LINK_RE.sub(r"\2", text)
    text = _PLAIN_LINK_RE.sub(r"\1", text)
    return text


def _split_long(text: str, max_chars: int, overlap: int) -> list[str]:
    """長い本文を max_chars 窓・overlap 重なりで分割する。"""
    if len(text) <= max_chars:
        return [text]
    step = max(1, max_chars - overlap)
    pieces: list[str] = []
    start = 0
    while start < len(text):
        pieces.append(text[start : start + max_chars])
        if start + max_chars >= len(text):
            break
        start += step
    return pieces


def chunk_text(
    markdown: str,
    *,
    title: str,
    rel_path: str,
    max_chars: int = _DEFAULT_MAX_CHARS,
    overlap: int = _DEFAULT_OVERLAP,
    min_chars: int = 1,
) -> list[dict]:
    """Markdown 本文をチャンク（dict）のリストに分割する。

    各チャンク: {id, path, title, heading, line_start, text}

    max_chars は「パンくず連結後に埋め込まれる実テキスト全体」の上限として扱う。
    パンくず分を本文側の予算から差し引いて分割するため、生成チャンクの text 長は
    max_chars を超えない（埋め込みモデルの入力上限超過による無言の切り捨てを防ぐ）。
    """
    body, offset = strip_frontmatter(markdown)
    lines = body.split("\n")
    n = len(lines)
    chunks: list[dict] = []
    counter = 0
    stack: list[tuple[int, str]] = []  # (level, text) — H1-H3 のみ

    def emit(heading_text: str, start_line: int, body_lines: list[str], breadcrumb: str) -> None:
        nonlocal counter
        body_raw = "\n".join(body_lines).strip()
        if len(body_raw) < min_chars:
            return
        body_norm = normalize_wikilinks(body_raw)
        # パンくず（+ 区切りの "\n\n"）の分を本文予算から差し引き、連結後の text が
        # max_chars を超えないようにする。overlap も予算内に収める。
        prefix_len = len(breadcrumb) + 2 if breadcrumb else 0
        piece_budget = max(_MIN_PIECE_CHARS, max_chars - prefix_len)
        eff_overlap = min(overlap, piece_budget // 2)
        for piece in _split_long(body_norm, piece_budget, eff_overlap):
            text = f"{breadcrumb}\n\n{piece}" if breadcrumb else piece
            chunks.append(
                {
                    "id": f"{rel_path}#{counter}",
                    "path": rel_path,
                    "title": title,
                    "heading": heading_text,
                    "line_start": start_line,
                    "text": text,
                }
            )
            counter += 1

    # 最初の見出しより前（前文）
    first_heading = next((i for i in range(n) if _HEADING_RE.match(lines[i])), n)
    if first_heading > 0:
        emit("", offset + 1, lines[:first_heading], title)

    i = first_heading
    while i < n:
        m = _HEADING_RE.match(lines[i])
        if not m:
            i += 1
            continue
        level = len(m.group(1))
        heading_text = m.group(2).strip()
        start_line = offset + i + 1

        while stack and stack[-1][0] >= level:
            stack.pop()
        if level <= _MAX_BREADCRUMB_LEVEL:
            stack.append((level, heading_text))
        breadcrumb = " > ".join([title, *(t for _, t in stack)])

        j = i + 1
        body_lines: list[str] = []
        while j < n and not _HEADING_RE.match(lines[j]):
            body_lines.append(lines[j])
            j += 1
        emit(heading_text, start_line, body_lines, breadcrumb)
        i = j

    return chunks


def chunk_file(path: Path, vault_dir: Path, **kwargs) -> list[dict]:
    """ファイルを読み込んでチャンク化する。title はファイル名（拡張子なし）。"""
    rel_path = path.relative_to(vault_dir).as_posix()
    text = path.read_text(encoding="utf-8", errors="replace")
    return chunk_text(text, title=path.stem, rel_path=rel_path, **kwargs)
