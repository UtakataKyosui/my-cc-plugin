"""クエリ埋め込みと numpy 総当たりによる top-k 検索。

埋め込みは L2 正規化済みのため、コサイン類似度を内積（embeddings @ q）で計算する。
embed_fn を注入すれば実モデルを読み込まずに（テスト等で）検索ロジックを使える。
"""

from __future__ import annotations

import re
from collections.abc import Callable
from pathlib import Path

import numpy as np

from .config import resolve_index_dir, resolve_vault_dir
from .models import make_embedder
from .store import IndexStore

_SNIPPET_CHARS = 140
_WS_RE = re.compile(r"\s+")


def rank(embeddings: np.ndarray, query_vec: np.ndarray, top_k: int) -> list[tuple[int, float]]:
    """類似度上位を (行 index, スコア) の降順リストで返す。"""
    if embeddings.shape[0] == 0:
        return []
    scores = embeddings @ query_vec
    k = min(top_k, scores.shape[0])
    if k < scores.shape[0]:
        candidate = np.argpartition(-scores, k - 1)[:k]
    else:
        candidate = np.arange(scores.shape[0])
    ordered = candidate[np.argsort(-scores[candidate])]
    return [(int(i), float(scores[i])) for i in ordered]


def _snippet(text: str) -> str:
    """チャンク本文から提示用の短いスニペットを作る（パンくず行は除く）。"""
    body = text.split("\n\n", 1)[-1]
    collapsed = _WS_RE.sub(" ", body).strip()
    return collapsed[:_SNIPPET_CHARS]


def search(
    query: str,
    top_k: int = 5,
    index_dir: Path | None = None,
    embed_fn: Callable[..., np.ndarray] | None = None,
) -> dict:
    """インデックスを読み込み、クエリに意味的に近いチャンクを返す。

    index_dir が None の場合は環境変数から Vault/インデックスパスを自動解決する。
    明示指定すると CLI 以外（テスト・外部呼び出し）から任意のインデックスを使える。
    """
    if index_dir is None:
        index_dir = resolve_index_dir(resolve_vault_dir())
    store = IndexStore(index_dir)
    if not store.exists():
        raise FileNotFoundError(
            f"インデックスが見つかりません: {index_dir}. `index` を先に実行してください。"
        )

    embeddings, chunks, manifest = store.load()
    # 3 ファイルは個別に原子的置換されるため、index と同時並行で読むと
    # 新しい embeddings と古い chunks を掴む可能性がある。行数の不一致は
    # IndexError ではなく明確なエラーにして再構築を促す。
    if embeddings.shape[0] != len(chunks):
        raise ValueError(
            f"インデックスが不整合です（ベクトル {embeddings.shape[0]} 行 / "
            f"チャンク {len(chunks)} 件）。`index --full` で再構築してください。"
        )
    if embed_fn is None:
        embed_fn = make_embedder(manifest["model"])

    query_vec = embed_fn([query], is_query=True)[0]
    ranked = rank(embeddings, query_vec, top_k)

    results = [
        {
            "path": chunks[idx]["path"],
            "score": round(score, 4),
            "heading": chunks[idx].get("heading", ""),
            "line_start": chunks[idx].get("line_start", 1),
            "snippet": _snippet(chunks[idx].get("text", "")),
        }
        for idx, score in ranked
    ]
    return {"query": query, "model": manifest.get("model"), "results": results}
