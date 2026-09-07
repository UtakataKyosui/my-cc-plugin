#!/usr/bin/env python3
"""extract_assets.py の出力を受け取り、役割重複クラスタを検出して JSON で出力する。

アルゴリズム:
  1. category_hint でバケット化
  2. バケット内で name 類似度 (SequenceMatcher) と
     description トークン Jaccard 類似度を計算
  3. しきい値超のペアを Union-Find で統合
  4. 2 メンバー以上のクラスタだけ出力
"""

import argparse
import json
import sys
from difflib import SequenceMatcher
from pathlib import Path


def _jaccard(set_a: set[str], set_b: set[str]) -> float:
    if not set_a and not set_b:
        return 1.0
    union = set_a | set_b
    if not union:
        return 0.0
    return len(set_a & set_b) / len(union)


def _name_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _name_matches(a: str, b: str, threshold: float) -> bool:
    """name の類似度判定。前後にドメインプレフィックス/サフィックスが付く場合も検出する。

    例: 'code-reviewer' vs 'rust-code-reviewer' → True (reviewer が共通 = 機能語)
        'code-debugger' vs 'rust-code-reviewer' → False (debugger/reviewer は異なる役割)
        'exit'          vs 'quit'               → SequenceMatcher で判断
    """
    na, nb = a.lower().replace("_", "-"), b.lower().replace("_", "-")
    if _name_similarity(na, nb) >= threshold:
        return True

    # 一方が他方を含む（ドメインプレフィックス除去後の一致）
    # 「ドメイン語」は共通ワードとしてカウントしない（rust, tauri, obs, zenn 等）
    _DOMAIN_NOISE = {
        "rust",
        "tauri",
        "obs",
        "zenn",
        "poml",
        "wasm",
        "activitypub",
        "code",
        "plugin",
    }
    parts_a = set(na.split("-")) - _DOMAIN_NOISE - {""}
    parts_b = set(nb.split("-")) - _DOMAIN_NOISE - {""}
    # 機能語（reviewer, debugger, optimizer, guide, tools 等）が 1 つ以上共通していれば一致
    common_functional = parts_a & parts_b
    return bool(common_functional and len(common_functional) >= 1)


class _UnionFind:
    def __init__(self, n: int) -> None:
        self._parent = list(range(n))
        self._rank = [0] * n

    def find(self, x: int) -> int:
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, x: int, y: int) -> None:
        rx, ry = self.find(x), self.find(y)
        if rx == ry:
            return
        if self._rank[rx] < self._rank[ry]:
            rx, ry = ry, rx
        self._parent[ry] = rx
        if self._rank[rx] == self._rank[ry]:
            self._rank[rx] += 1


def cluster(
    assets: list[dict],
    *,
    jaccard_threshold: float = 0.40,
    name_threshold: float = 0.85,
) -> list[dict]:
    """assets をクラスタリングして cluster リストを返す."""
    # category_hint ごとにバケット化
    buckets: dict[str, list[int]] = {}
    for i, asset in enumerate(assets):
        cat = asset.get("category_hint", "other")
        buckets.setdefault(cat, []).append(i)

    n = len(assets)
    uf = _UnionFind(n)
    # クラスタ内のペア間の最大類似度を記録（Issue 本文用）
    pair_scores: list[dict] = []

    for _cat, indices in buckets.items():
        for ii, i in enumerate(indices):
            for j in indices[ii + 1 :]:
                a, b = assets[i], assets[j]
                tokens_a = set(a.get("tokens", []))
                tokens_b = set(b.get("tokens", []))
                jac = _jaccard(tokens_a, tokens_b)
                name_sim = _name_similarity(a["name"], b["name"])
                # 同名 or 類似度がしきい値超 or 名前が部分一致 → 同一クラスタ
                if (
                    _name_matches(a["name"], b["name"], name_threshold)
                    or jac >= jaccard_threshold
                ):
                    uf.union(i, j)
                    pair_scores.append(
                        {
                            "a": a["id"],
                            "b": b["id"],
                            "jaccard": round(jac, 3),
                            "name_sim": round(name_sim, 3),
                        }
                    )

    # Union-Find のルートでグループ化
    groups: dict[int, list[int]] = {}
    for i in range(n):
        root = uf.find(i)
        groups.setdefault(root, []).append(i)

    # 2 メンバー以上のグループをクラスタとして出力
    clusters: list[dict] = []
    cluster_counter: dict[str, int] = {}
    for _root, indices in sorted(groups.items()):
        if len(indices) < 2:
            continue
        members = [assets[i] for i in indices]
        cat = members[0].get("category_hint", "other")
        cluster_counter[cat] = cluster_counter.get(cat, 0) + 1
        cluster_id = f"{cat}-{cluster_counter[cat]:03d}"

        # このクラスタのペアスコアを集計
        member_ids = {m["id"] for m in members}
        relevant_pairs = [
            p for p in pair_scores if p["a"] in member_ids and p["b"] in member_ids
        ]
        max_jaccard = max((p["jaccard"] for p in relevant_pairs), default=0.0)

        clusters.append(
            {
                "cluster_id": cluster_id,
                "category": cat,
                "max_jaccard": max_jaccard,
                "member_count": len(members),
                "members": members,
                "pair_scores": relevant_pairs,
            }
        )

    # category → member_count の順でソート
    clusters.sort(key=lambda c: (c["category"], -c["member_count"]))
    return clusters


def main() -> None:
    parser = argparse.ArgumentParser(
        description="extract_assets.py の出力からクラスタを検出する"
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="-",
        help="extract_assets.py の JSON 出力ファイル。- で標準入力 (デフォルト: -)",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="出力先ファイルパス。- で標準出力 (デフォルト: -)",
    )
    parser.add_argument(
        "--jaccard",
        type=float,
        default=0.40,
        help="Jaccard 類似度しきい値 (デフォルト: 0.40)",
    )
    parser.add_argument(
        "--name-sim",
        type=float,
        default=0.85,
        help="name SequenceMatcher 類似度しきい値 (デフォルト: 0.85)",
    )
    args = parser.parse_args()

    if args.input == "-":
        raw = sys.stdin.read()
    else:
        raw = Path(args.input).read_text(encoding="utf-8")

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"[cluster_assets] ERROR: JSON parse failed: {e}", file=sys.stderr)
        sys.exit(1)

    assets = data.get("assets", [])
    clusters = cluster(
        assets, jaccard_threshold=args.jaccard, name_threshold=args.name_sim
    )

    result = json.dumps(
        {"cluster_count": len(clusters), "clusters": clusters},
        ensure_ascii=False,
        indent=2,
    )

    if args.output == "-":
        print(result)
    else:
        Path(args.output).write_text(result, encoding="utf-8")
        print(
            f"[cluster_assets] {len(clusters)} clusters written to {args.output}",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
