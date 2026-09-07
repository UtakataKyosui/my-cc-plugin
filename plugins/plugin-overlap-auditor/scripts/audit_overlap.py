#!/usr/bin/env python3
"""役割重複監査のオーケストレーター。

フロー:
  1. extract_assets.py → assets JSON
  2. cluster_assets.py → clusters JSON
  3. (--dry-run または --post-issues) 向けに clusters を出力
     LLM 分類 (overlap-classifier Agent) は Claude Code コマンド側で実行。

このスクリプトはステップ 1-2 を連携し、
Agent への入力 JSON を標準出力または --output に書き出す。
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS_DIR = Path(__file__).parent


def run_extract(scope: str, plugins_dir: str) -> dict:
    result = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "python3",
            str(SCRIPTS_DIR / "extract_assets.py"),
            "--scope",
            scope,
            "--plugins-dir",
            plugins_dir,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(
            f"[audit_overlap] extract_assets.py failed:\n{result.stderr}",
            file=sys.stderr,
        )
        sys.exit(1)
    return json.loads(result.stdout)


def run_cluster(assets_data: dict, jaccard: float, name_sim: float) -> dict:
    input_json = json.dumps(assets_data, ensure_ascii=False)
    result = subprocess.run(  # noqa: S603
        [  # noqa: S607
            "python3",
            str(SCRIPTS_DIR / "cluster_assets.py"),
            "--jaccard",
            str(jaccard),
            "--name-sim",
            str(name_sim),
        ],
        input=input_json,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        print(
            f"[audit_overlap] cluster_assets.py failed:\n{result.stderr}",
            file=sys.stderr,
        )
        sys.exit(1)
    return json.loads(result.stdout)


def print_summary(clusters_data: dict) -> None:
    """--summary オプション用のサマリを stderr に出力する（stdout の JSON 出力と競合しない）."""
    clusters = clusters_data.get("clusters", [])
    total = clusters_data.get("cluster_count", len(clusters))
    print(f"\n=== overlap-audit: {total} クラスタ検出 ===\n", file=sys.stderr)
    for c in clusters:
        members_str = ", ".join(
            f"{m['name']} ({m['source']}:{m.get('plugin', '')})" for m in c["members"]
        )
        print(
            f"  [{c['cluster_id']}] {c['category']} — "
            f"Jaccard max={c['max_jaccard']:.2f} — {c['member_count']} 件",
            file=sys.stderr,
        )
        print(f"    {members_str}", file=sys.stderr)
    print(file=sys.stderr)


def main() -> None:
    plugin_root = Path(__file__).parent.parent
    default_plugins_dir = str(plugin_root.parent)

    parser = argparse.ArgumentParser(
        description="役割重複監査: extract → cluster → (Agent 入力 JSON を出力)"
    )
    parser.add_argument(
        "--scope",
        default="all",
        help="監査スコープ: repo,user-global,marketplace,builtin または all (デフォルト: all)",
    )
    parser.add_argument(
        "--plugins-dir",
        default=default_plugins_dir,
        help=f"C2Lab plugins/ ディレクトリ (デフォルト: {default_plugins_dir})",
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
        help="name 類似度しきい値 (デフォルト: 0.85)",
    )
    parser.add_argument(
        "--output",
        default="-",
        help="クラスタ JSON の出力先。- で標準出力 (デフォルト: -)",
    )
    parser.add_argument(
        "--summary",
        action="store_true",
        help="クラスタのサマリを標準エラーに出力する",
    )
    args = parser.parse_args()

    print("[audit_overlap] Step 1: アセット抽出中...", file=sys.stderr)
    assets_data = run_extract(args.scope, args.plugins_dir)
    print(
        f"[audit_overlap] {assets_data.get('count', 0)} アセット抽出完了",
        file=sys.stderr,
    )

    print("[audit_overlap] Step 2: クラスタリング中...", file=sys.stderr)
    clusters_data = run_cluster(assets_data, args.jaccard, args.name_sim)
    print(
        f"[audit_overlap] {clusters_data.get('cluster_count', 0)} クラスタ検出",
        file=sys.stderr,
    )

    if args.summary:
        print_summary(clusters_data)

    output_json = json.dumps(clusters_data, ensure_ascii=False, indent=2)
    if args.output == "-":
        print(output_json)
    else:
        Path(args.output).write_text(output_json, encoding="utf-8")
        print(
            f"[audit_overlap] clusters JSON written to {args.output}", file=sys.stderr
        )


if __name__ == "__main__":
    main()
