"""Vault の走査・増分差分・インデックス構築。

ファイルの mtime/size を manifest と比較し、変更・新規のみ再埋め込みして
削除を反映する。埋め込みは embed_fn を注入でき、テストでは実モデルを使わない。
"""

from __future__ import annotations

import os
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from .chunker import chunk_file
from .config import EXCLUDE_DIRS, MARKDOWN_SUFFIXES
from .models import make_embedder
from .store import IndexStore


def scan_files(vault_dir: Path) -> dict[str, dict]:
    """Vault 内の対象 Markdown を走査し {rel_path: {mtime, size}} を返す。

    `os.walk` の dirnames in-place 剪定で除外ディレクトリ配下をそもそも降りないため、
    `rglob("*")` より大幅に I/O が少ない。
    """
    result: dict[str, dict] = {}
    for dirpath, dirnames, filenames in os.walk(vault_dir):
        # ドット始まり（.obsidian, .git 等）と EXCLUDE_DIRS を in-place で剪定する。
        # ここで削除したディレクトリには os.walk が降りなくなる。
        dirnames[:] = [
            d for d in dirnames
            if not d.startswith(".") and d not in EXCLUDE_DIRS
        ]
        for filename in filenames:
            if Path(filename).suffix.lower() not in MARKDOWN_SUFFIXES:
                continue
            if filename.startswith("."):
                continue
            full_path = Path(dirpath) / filename
            rel = full_path.relative_to(vault_dir)
            st = full_path.stat()
            result[rel.as_posix()] = {"mtime": st.st_mtime, "size": st.st_size}
    return result


def diff_manifest(old_manifest: dict, scanned: dict[str, dict]) -> tuple[set[str], set[str]]:
    """(再インデックス対象, 削除対象) を返す。"""
    old_files = old_manifest.get("files", {})
    to_index = {
        rel
        for rel, meta in scanned.items()
        if rel not in old_files
        or old_files[rel].get("mtime") != meta["mtime"]
        or old_files[rel].get("size") != meta["size"]
    }
    to_delete = set(old_files) - set(scanned)
    return to_index, to_delete


def build_index(
    vault_dir: Path,
    index_dir: Path,
    model_name: str,
    full: bool = False,
    embed_fn: Callable[..., np.ndarray] | None = None,
) -> dict:
    """インデックスを構築（全 or 増分）し、サマリ dict を返す。"""
    store = IndexStore(index_dir)
    scanned = scan_files(vault_dir)

    incremental = not full and store.exists()
    if incremental:
        old_embeddings, old_chunks, old_manifest = store.load()
        existing_model = old_manifest.get("model", model_name)
        if existing_model != model_name:
            raise ValueError(
                f"モデルが変わりました（{existing_model} → {model_name}）。"
                "`index --full` で再構築してください。"
            )
        to_index, to_delete = diff_manifest(old_manifest, scanned)
        if not to_index and not to_delete:
            return {
                "files": len(scanned),
                "chunks": len(old_chunks),
                "reindexed": 0,
                "deleted": 0,
                "up_to_date": True,
            }
    else:
        old_embeddings, old_chunks = None, []
        to_index, to_delete = set(scanned), set()

    if embed_fn is None:
        embed_fn = make_embedder(model_name)

    # 残存チャンク（再インデックス・削除対象でないファイル）を引き継ぐ
    surviving_chunks: list[dict] = []
    surviving_rows: list[int] = []
    if incremental and old_embeddings is not None:
        drop = to_index | to_delete
        for row, chunk in enumerate(old_chunks):
            if chunk["path"] not in drop:
                surviving_chunks.append(chunk)
                surviving_rows.append(row)

    # 新規・変更ファイルをチャンク化
    new_chunks: list[dict] = []
    for rel in sorted(to_index):
        path = vault_dir / rel
        if path.is_file():
            new_chunks.extend(chunk_file(path, vault_dir))

    new_embeddings = (
        embed_fn([c["text"] for c in new_chunks], is_query=False) if new_chunks else None
    )

    parts = []
    if surviving_rows:
        parts.append(old_embeddings[surviving_rows])
    if new_embeddings is not None and len(new_embeddings) > 0:
        parts.append(new_embeddings)

    chunks = surviving_chunks + new_chunks
    if parts:
        embeddings = np.vstack(parts).astype("float32")
    else:
        embeddings = np.zeros((0, 0), dtype="float32")

    manifest = {
        "model": model_name,
        "dim": int(embeddings.shape[1]) if embeddings.ndim == 2 and embeddings.shape[0] else 0,
        "files": scanned,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    store.save(embeddings, chunks, manifest)

    return {
        "files": len(scanned),
        "chunks": len(chunks),
        "reindexed": len(to_index),
        "deleted": len(to_delete),
        "up_to_date": False,
    }
