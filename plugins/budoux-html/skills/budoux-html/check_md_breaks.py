import sys, re, budoux
p = budoux.load_default_japanese_parser()
lines = open(sys.argv[1], encoding="utf-8").read().split("\n")
in_code = False; in_fm = False; para = []
def skip(l):
    s = l.strip()
    return (not s or s.startswith(("|", "#", ":::", ">", "- ", "```", "<", "!", "[^")) or re.match(r"^\d+\. ", s))
def flush(para):
    for i in range(len(para) - 1):
        n, a = para[i]; _, b = para[i + 1]
        text = a + b
        chunks = p.parse(text)
        pos, bounds = 0, {0}
        for c in chunks:
            pos += len(c); bounds.add(pos)
        if len(a) not in bounds:
            tail = a[-8:]; head = b[:8]
            print(f"{n}: …{tail} | {head}…  budoux={'/'.join(chunks)[max(0,len(a)-15):len(a)+15]}")
for idx, l in enumerate(lines, 1):
    if idx == 1 and l == "---": in_fm = True; continue
    if in_fm:
        if l == "---": in_fm = False
        continue
    if l.strip().startswith("```"):
        in_code = not in_code; flush(para); para = []; continue
    if in_code or skip(l):
        flush(para); para = []; continue
    para.append((idx, l))
flush(para)
