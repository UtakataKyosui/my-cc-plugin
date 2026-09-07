"""インデックスの永続化（embeddings.npy / chunks.jsonl / manifest.json）。

数千チャンク規模では faiss 不要。埋め込みは numpy の float32 行列で持ち、
メタデータは行と同順の JSONL、manifest にモデル・次元・ファイル mtime を記録する。
書き込みは tmp → os.replace で原子的に行い、途中失敗で旧インデックスを壊さない。
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np


class IndexStore:
    """`<index_dir>/` 配下の3ファイルを読み書きする。"""

    def __init__(self, index_dir: Path) -> None:
        self.index_dir = Path(index_dir)
        self.embeddings_path = self.index_dir / "embeddings.npy"
        self.chunks_path = self.index_dir / "chunks.jsonl"
        self.manifest_path = self.index_dir / "manifest.json"

    def exists(self) -> bool:
        return (
            self.embeddings_path.is_file()
            and self.chunks_path.is_file()
            and self.manifest_path.is_file()
        )

    def load(self) -> tuple[np.ndarray, list[dict], dict]:
        embeddings = np.load(self.embeddings_path)
        chunks = [
            json.loads(line)
            for line in self.chunks_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        return embeddings, chunks, manifest

    def save(self, embeddings: np.ndarray, chunks: list[dict], manifest: dict) -> None:
        self.index_dir.mkdir(parents=True, exist_ok=True)

        emb_tmp = self.embeddings_path.with_suffix(".npy.tmp")
        # ファイルハンドルを渡す: パス渡しだと np.save が .npy を付け足して
        # tmp 名が変わり、後段の os.replace が失敗する。
        with emb_tmp.open("wb") as f:
            np.save(f, embeddings.astype("float32"))
        os.replace(emb_tmp, self.embeddings_path)

        chunks_tmp = self.chunks_path.with_suffix(".jsonl.tmp")
        with chunks_tmp.open("w", encoding="utf-8") as f:
            for chunk in chunks:
                f.write(json.dumps(chunk, ensure_ascii=False) + "\n")
        os.replace(chunks_tmp, self.chunks_path)

        manifest_tmp = self.manifest_path.with_suffix(".json.tmp")
        manifest_tmp.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        os.replace(manifest_tmp, self.manifest_path)
