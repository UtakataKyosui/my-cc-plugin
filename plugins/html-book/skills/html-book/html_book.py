#!/usr/bin/env python3
"""レポート形式の HTML を、ページをめくる本の形の HTML に変換する。

使い方: python html_book.py <input.html> <output.html>

入力の前提:
- <main> の直下に <h2> と <h3> が並ぶ構成であること
- <header> があれば表紙に使う（h1 と p を拾う）
- <style> はそのまま引き継ぐ

ページの切り方: <h2> または <h3> ごとに新しいページを始める。ただし <h2> の直後に
<h3> が来るまでの間は同じページにまとめる（章の導入と最初の節を 1 ページにする）。
<main> 直下の最初の <h2> より前にある要素は表紙に載せる。
"""
import html
import re
import sys

VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr"}
TAG = re.compile(r"<!--.*?-->|<(/?)([a-zA-Z][a-zA-Z0-9]*)\b[^>]*?(/?)>", re.S)


def top_level_elements(fragment: str) -> list[str]:
    """fragment を直下の要素（とテキスト）の列に分ける。"""
    out, depth, start, pos = [], 0, None, 0
    for m in TAG.finditer(fragment):
        if m.group(0).startswith("<!--"):
            continue
        closing, name, selfclose = m.group(1), m.group(2).lower(), m.group(3)
        if depth == 0 and not closing:
            text = fragment[pos:m.start()]
            if text.strip():
                out.append(text)
            start = m.start()
        if name in VOID or selfclose:
            if depth == 0:
                out.append(fragment[start:m.end()])
                pos = m.end()
            continue
        if closing:
            depth -= 1
            if depth == 0:
                out.append(fragment[start:m.end()])
                pos = m.end()
        else:
            depth += 1
    return out


def tag_of(el: str) -> str:
    m = re.match(r"\s*<([a-zA-Z0-9]+)", el)
    return m.group(1).lower() if m else ""


def inner(el: str) -> str:
    return re.sub(r"^\s*<[^>]+>|</[^>]+>\s*$", "", el, count=2).strip()


def plain(s: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", s)).strip()


def build_pages(main_html: str):
    cover, pages, chapter = [], [], ""
    for el in top_level_elements(main_html):
        t = tag_of(el)
        if t == "h2":
            chapter = inner(el)
            pages.append({"chapter": chapter, "title": chapter, "body": [el], "has_h3": False})
        elif t == "h3":
            if pages and pages[-1]["chapter"] == chapter and not pages[-1]["has_h3"] and chapter:
                pages[-1]["body"].append(el)
                pages[-1]["title"] = inner(el)
                pages[-1]["has_h3"] = True
            else:
                pages.append({"chapter": chapter, "title": inner(el), "body": [el], "has_h3": True})
        elif pages:
            pages[-1]["body"].append(el)
        else:
            cover.append(el)
    return cover, pages


BOOK_CSS = """
  html, body { height: 100%; }
  body.book-mode {
    margin: 0; background: #2f3437; overflow: hidden;
    display: flex; flex-direction: column; align-items: center;
  }
  .book {
    position: relative; flex: 1; width: min(1120px, calc(100vw - 32px));
    margin: 16px 0 8px; perspective: 2400px;
  }
  .page {
    position: absolute; inset: 0; display: flex; flex-direction: column;
    background: #fffdf8; border-radius: 4px 10px 10px 4px;
    box-shadow: inset 14px 0 18px -14px rgba(0,0,0,.25);
    transform-origin: left center; transform-style: preserve-3d;
    transition: transform .7s cubic-bezier(.3,.7,.2,1), opacity .1s linear, box-shadow .7s;
    backface-visibility: hidden;
  }
  .page.current { box-shadow: 0 10px 30px rgba(0,0,0,.35), inset 14px 0 18px -14px rgba(0,0,0,.25); }
  .page.turned {
    transform: rotateY(-100deg); opacity: 0; pointer-events: none; box-shadow: none;
    transition: transform .7s cubic-bezier(.3,.7,.2,1), opacity .15s linear .5s, box-shadow .7s;
  }
  .page-head {
    display: flex; justify-content: space-between; gap: 16px;
    padding: 14px 40px 8px; font-size: 12px; color: #8a8173;
    border-bottom: 1px solid #eee6d8;
  }
  .page-body { flex: 1; overflow: auto; padding: 8px 40px 24px; }
  .page-body > h2:first-child, .page-body > h3:first-child { margin-top: 16px; }
  .page-foot { padding: 8px 40px 12px; text-align: center; font-size: 12px; color: #8a8173; border-top: 1px solid #eee6d8; }
  .page-foot .more { display: none; margin-right: 12px; color: #9a6700; font-weight: 600; }
  .page.has-more .page-foot .more { display: inline; }
  .page.has-more .page-body { mask-image: linear-gradient(to bottom, #000 calc(100% - 40px), transparent); }
  .cover .page-body { display: flex; flex-direction: column; justify-content: center; }
  .cover h1 { font-size: 30px; line-height: 1.45; margin: 0 0 16px; color: #0d2b45; }
  .cover .meta { color: #59636e; font-size: 13px; margin: 2px 0; }
  .cover .toc-list { margin: 24px 0 0; padding: 0; list-style: none; columns: 2; column-gap: 40px; }
  .cover .toc-list li { break-inside: avoid; margin: 3px 0; }
  .cover .toc-list li.sub { padding-left: 1.4em; }
  .cover .toc-list li.chapter { margin-top: 10px; }
  .cover .toc-list button {
    all: unset; cursor: pointer; color: #1f6feb;
  }
  .cover .toc-list button:hover, .cover .toc-list button:focus-visible { text-decoration: underline; outline: none; }
  .cover .toc-list .chap { font-weight: 600; }
  .cover .toc-list span.chap { color: #1f2328; }
  .edge {
    position: absolute; top: 0; bottom: 0; width: 44px; z-index: 1000;
    border: 0; background: transparent; cursor: pointer; color: rgba(255,255,255,.0);
    font-size: 28px;
  }
  .edge:hover, .edge:focus-visible { color: rgba(255,255,255,.85); outline: none; }
  .edge.prev { left: -44px; }
  .edge.next { right: -44px; }
  .edge:disabled { cursor: default; color: transparent; }
  .book-nav {
    display: flex; align-items: center; gap: 12px; padding: 6px 0 14px; color: #e6e1d6; font-size: 13px;
  }
  .book-nav button, .book-nav select {
    font: inherit; color: #1f2328; background: #f3efe6; border: 0; border-radius: 6px;
    padding: 6px 14px; cursor: pointer; min-height: 32px;
  }
  .book-nav button:disabled { opacity: .4; cursor: default; }
  .book-nav select { max-width: 46vw; }
  .book-nav .hint { color: #a9a396; font-size: 12px; }
  .book-nav button, #counter { white-space: nowrap; }
  @media (max-width: 760px) {
    .page-head, .page-body, .page-foot { padding-left: 16px; padding-right: 16px; }
    .edge { display: none; }
    .book-nav .hint { display: none; }
    .book-nav { gap: 6px; }
    .book-nav button { padding: 6px 10px; }
    .book-nav select { max-width: 40vw; }
    .cover .toc-list { columns: 1; }
  }
  @media (prefers-reduced-motion: reduce) { .page { transition: none; } }
  @media print {
    body.book-mode { overflow: visible; display: block; background: #fff; }
    .book { perspective: none; width: auto; margin: 0; }
    .page { position: static; transform: none !important; opacity: 1 !important; box-shadow: none; break-after: page; }
    .page-body { overflow: visible; }
    .book-nav, .edge { display: none; }
  }
"""

BOOK_JS = """
(() => {
  const pages = [...document.querySelectorAll('.page')];
  const prev = document.getElementById('prev'), next = document.getElementById('next');
  const ePrev = document.getElementById('edge-prev'), eNext = document.getElementById('edge-next');
  const counter = document.getElementById('counter'), jump = document.getElementById('jump');
  let cur = 0;
  pages.forEach((p, i) => { p.style.zIndex = String(pages.length - i); });
  function show(i) {
    i = Math.max(0, Math.min(pages.length - 1, i));
    pages.forEach((p, k) => {
      p.classList.toggle('turned', k < i);
      p.classList.toggle('current', k === i);
      p.inert = k !== i;
      p.setAttribute('aria-hidden', String(k !== i));
    });
    cur = i;
    counter.textContent = `${i + 1} / ${pages.length}`;
    prev.disabled = ePrev.disabled = i === 0;
    next.disabled = eNext.disabled = i === pages.length - 1;
    jump.value = String(i);
    history.replaceState(null, '', '#p' + (i + 1));
    checkMore(pages[i]);
  }
  function checkMore(p) {
    const b = p.querySelector('.page-body');
    p.classList.toggle('has-more', b.scrollHeight - b.scrollTop - b.clientHeight > 8);
  }
  pages.forEach(p => p.querySelector('.page-body').addEventListener('scroll', () => checkMore(p), { passive: true }));
  window.addEventListener('resize', () => checkMore(pages[cur]));
  const go = d => show(cur + d);
  prev.onclick = ePrev.onclick = () => go(-1);
  next.onclick = eNext.onclick = () => go(1);
  jump.onchange = () => show(Number(jump.value));
  document.querySelectorAll('[data-goto]').forEach(b => { b.onclick = () => show(Number(b.dataset.goto)); });
  document.addEventListener('keydown', e => {
    if (e.target.closest('select, input, textarea')) return;
    if (['ArrowRight', 'PageDown'].includes(e.key)) { e.preventDefault(); go(1); }
    else if (['ArrowLeft', 'PageUp'].includes(e.key)) { e.preventDefault(); go(-1); }
    else if (e.key === 'Home') { e.preventDefault(); show(0); }
    else if (e.key === 'End') { e.preventDefault(); show(pages.length - 1); }
  });
  let sx = null, sy = null;
  const book = document.querySelector('.book');
  book.addEventListener('touchstart', e => { sx = e.touches[0].clientX; sy = e.touches[0].clientY; }, { passive: true });
  book.addEventListener('touchend', e => {
    if (sx === null) return;
    const dx = e.changedTouches[0].clientX - sx, dy = e.changedTouches[0].clientY - sy;
    if (Math.abs(dx) > 60 && Math.abs(dx) > Math.abs(dy) * 1.5) go(dx < 0 ? 1 : -1);
    sx = sy = null;
  });
  const m = location.hash.match(/^#p(\\d+)$/);
  show(m ? Number(m[1]) - 1 : 0);
})();
"""


def render(src: str) -> str:
    style = "\n".join(re.findall(r"<style>(.*?)</style>", src, re.S))
    title = re.search(r"<title>(.*?)</title>", src, re.S)
    title = title.group(1) if title else "レポート"
    header = re.search(r"<header[^>]*>(.*?)</header>", src, re.S)
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", header.group(1), re.S).group(1) if header else title
    metas = re.findall(r"<p[^>]*>(.*?)</p>", header.group(1), re.S) if header else []
    main = re.search(r"<main[^>]*>(.*?)</main>", src, re.S).group(1)
    cover_extra, pages = build_pages(main)

    toc, last_chap = [], None
    for i, p in enumerate(pages, start=1):
        if p["chapter"] != last_chap:
            if p["title"] == p["chapter"]:
                toc.append(f'<li class="chapter"><button type="button" class="chap" data-goto="{i}">{p["chapter"]}</button></li>')
            else:
                toc.append(f'<li class="chapter"><span class="chap">{p["chapter"]}</span></li>')
            last_chap = p["chapter"]
        if p["title"] != p["chapter"]:
            toc.append(f'<li class="sub"><button type="button" data-goto="{i}">{p["title"]}</button></li>')

    total = len(pages) + 1
    sections = [
        f'<section class="page cover" aria-label="表紙">\n<div class="page-head"><span>{title}</span><span>表紙</span></div>\n'
        f'<div class="page-body">\n<h1>{h1}</h1>\n'
        + "".join(f'<p class="meta">{m}</p>\n' for m in metas)
        + "".join(cover_extra)
        + f'\n<ul class="toc-list" aria-label="目次">\n' + "\n".join(toc) + "\n</ul>\n</div>\n"
        f'<div class="page-foot">1 / {total}</div>\n</section>'
    ]
    options = ['<option value="0">表紙</option>']
    for i, p in enumerate(pages, start=1):
        label = plain(p["title"])
        options.append(f'<option value="{i}">{html.escape(label)}</option>')
        sections.append(
            f'<section class="page" aria-label="{html.escape(label)}">\n'
            f'<div class="page-head"><span>{p["chapter"]}</span><span>{i + 1}</span></div>\n'
            f'<div class="page-body">\n' + "\n".join(p["body"]) + "\n</div>\n"
            f'<div class="page-foot"><span class="more">▼ 下に続きがあります</span>{i + 1} / {total}</div>\n</section>'
        )

    return f"""<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
{style}
{BOOK_CSS}
</style>
</head>
<body class="book-mode">
<div class="book">
<button type="button" class="edge prev" id="edge-prev" aria-label="前のページ">‹</button>
{chr(10).join(sections)}
<button type="button" class="edge next" id="edge-next" aria-label="次のページ">›</button>
</div>
<nav class="book-nav" aria-label="ページ送り">
  <button type="button" id="prev">← 前へ</button>
  <select id="jump" aria-label="ページを選ぶ">{"".join(options)}</select>
  <span id="counter" aria-live="polite"></span>
  <button type="button" id="next">次へ →</button>
  <span class="hint">← → キーでもめくれます</span>
</nav>
<script>{BOOK_JS}</script>
</body>
</html>
"""


def main(argv: list[str]) -> None:
    if len(argv) != 3:
        sys.exit(__doc__)
    with open(argv[1], encoding="utf-8") as f:
        src = f.read()
    out = render(src)
    with open(argv[2], "w", encoding="utf-8") as f:
        f.write(out)
    n = len(re.findall(r'<section class="page', out))
    print(f"{argv[2]}: {n} pages")


if __name__ == "__main__":
    main(sys.argv)
