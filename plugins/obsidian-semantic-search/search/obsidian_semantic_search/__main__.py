"""CLI エントリポイント: `python -m obsidian_semantic_search <index|query|status>`。

status はインデックスの manifest と Vault の mtime 走査だけで判定し、
埋め込みモデルをロードしないため高速（SessionStart フックから安全に呼べる）。
"""

from __future__ import annotations

import argparse
import json
import sys

from .config import get_model_name, resolve_index_dir, resolve_vault_dir
from .indexer import build_index, diff_manifest, scan_files
from .search import search
from .store import IndexStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="obsidian-semantic-search",
        description="Obsidian Vault のローカル意味検索",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_index = sub.add_parser("index", help="インデックスを構築（増分が既定）")
    p_index.add_argument("--full", action="store_true", help="全再構築")

    p_query = sub.add_parser("query", help="意味検索")
    p_query.add_argument("text", help="検索クエリ")
    p_query.add_argument("--top-k", type=int, default=5, dest="top_k", help="返す件数")
    p_query.add_argument("--json", action="store_true", help="JSON 出力")

    p_status = sub.add_parser("status", help="インデックスの状態")
    p_status.add_argument("--json", action="store_true", help="JSON 出力")

    return parser


def _cmd_index(args) -> int:
    vault = resolve_vault_dir()
    index_dir = resolve_index_dir(vault)
    model = get_model_name()
    print(f"Vault: {vault}\nIndex: {index_dir}\nModel: {model}", file=sys.stderr)
    try:
        summary = build_index(vault, index_dir, model, full=args.full)
    except ValueError as exc:
        # 主にモデル変更による次元/モデル不一致。生のトレースバックを出さず案内する。
        print(str(exc), file=sys.stderr)
        return 1
    if summary.get("up_to_date"):
        print(f"up-to-date（{summary['files']} ファイル / {summary['chunks']} チャンク）")
    else:
        print(
            f"インデックス更新: {summary['files']} ファイル / {summary['chunks']} チャンク "
            f"(再インデックス {summary['reindexed']} / 削除 {summary['deleted']})"
        )
    return 0


def _cmd_query(args) -> int:
    vault = resolve_vault_dir()
    index_dir = resolve_index_dir(vault)
    try:
        result = search(args.text, top_k=args.top_k, index_dir=index_dir)
    except (FileNotFoundError, ValueError) as exc:
        # 未構築（FileNotFoundError）/ 不整合・モデル不一致（ValueError）を案内する。
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(result, ensure_ascii=False))
    else:
        for r in result["results"]:
            print(f"[{r['score']:.3f}] {r['path']}:{r['line_start']}  〈{r['heading']}〉")
            print(f"    {r['snippet']}")
    return 0


def _cmd_status(args) -> int:
    vault = resolve_vault_dir()
    index_dir = resolve_index_dir(vault)
    store = IndexStore(index_dir)

    if not store.exists():
        out = {
            "indexed": False,
            "missing_index": True,
            "model": get_model_name(),
            "chunks": 0,
            "files": 0,
            "stale": 0,
        }
    else:
        manifest = json.loads(store.manifest_path.read_text(encoding="utf-8"))
        chunk_count = sum(
            1 for line in store.chunks_path.read_text(encoding="utf-8").splitlines() if line.strip()
        )
        to_index, to_delete = diff_manifest(manifest, scan_files(vault))
        out = {
            "indexed": True,
            "missing_index": False,
            "model": manifest.get("model"),
            "chunks": chunk_count,
            "files": len(manifest.get("files", {})),
            "stale": len(to_index | to_delete),
            "updated_at": manifest.get("updated_at"),
        }

    if args.json:
        print(json.dumps(out, ensure_ascii=False))
    elif out["missing_index"]:
        print("インデックス未構築です。`index` を実行してください。")
    else:
        print(
            f"indexed: {out['files']} ファイル / {out['chunks']} チャンク / "
            f"model={out['model']} / 未更新 {out['stale']} 件"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    handlers = {"index": _cmd_index, "query": _cmd_query, "status": _cmd_status}
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
