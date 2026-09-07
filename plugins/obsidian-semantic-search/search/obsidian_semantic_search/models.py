"""埋め込みモデルのレジストリとロード。

モデルごとに query / passage プレフィックス（e5 系の `query: `/`passage: ` 等）が
異なるため、レジストリで一元管理する。SentenceTransformer のロードは重いので
遅延 import とし、status のような軽量コマンドでは読み込まない。
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # 型のみ。実行時に numpy/sentence-transformers を強制しない。
    import numpy as np

# モデル名 → (query_prefix, passage_prefix)。
# e5 系は非対称検索用にプレフィックスが必須。ruri 系は日本語の指示文を使う。
MODEL_PREFIXES: dict[str, tuple[str, str]] = {
    "intfloat/multilingual-e5-small": ("query: ", "passage: "),
    "intfloat/multilingual-e5-base": ("query: ", "passage: "),
    "intfloat/multilingual-e5-large": ("query: ", "passage: "),
    "cl-nagoya/ruri-v3-30m": ("検索クエリ: ", "検索文書: "),
    "cl-nagoya/ruri-base": ("検索クエリ: ", "検索文書: "),
}


def query_prefix(model_name: str) -> str:
    """検索クエリ側に付与するプレフィックス（未知モデルは空文字）。"""
    return MODEL_PREFIXES.get(model_name, ("", ""))[0]


def passage_prefix(model_name: str) -> str:
    """文書（passage）側に付与するプレフィックス（未知モデルは空文字）。"""
    return MODEL_PREFIXES.get(model_name, ("", ""))[1]


def load_model(model_name: str):
    """SentenceTransformer をロードして返す（遅延 import）。"""
    from sentence_transformers import SentenceTransformer

    return SentenceTransformer(model_name)


def make_embedder(model_name: str) -> Callable[..., "np.ndarray"]:
    """`(texts, *, is_query) -> np.ndarray` の埋め込み関数を生成する。

    is_query に応じてプレフィックスを付け、L2 正規化済みの float32 行列を返す。
    正規化済みなので、後段ではコサイン類似度を内積で計算できる。
    """
    model = load_model(model_name)
    qp = query_prefix(model_name)
    pp = passage_prefix(model_name)

    def embed(texts: list[str], *, is_query: bool = False) -> "np.ndarray":
        prefix = qp if is_query else pp
        prepared = [f"{prefix}{t}" for t in texts]
        vecs = model.encode(
            prepared,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return vecs.astype("float32")

    return embed
