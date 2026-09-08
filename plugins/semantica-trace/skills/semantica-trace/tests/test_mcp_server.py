"""照会 MCP サーバーが保証すべき性質を固定する。

対象は「壊れると黙って誤答する」経路だけに絞る。
"""

from __future__ import annotations

import importlib.util
import io
import os
import subprocess
import sys

import pytest

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(HERE)


def _load_module():
    """mcp_server.py を import する。import 時点の stdout も一緒に返す。

    stdio トランスポートは stdout が JSON-RPC 専用のため、import が何か
    print すればプロトコルが壊れる。ここで捕まえて検査する。
    """
    captured = io.StringIO()
    real_stdout = sys.stdout
    sys.stdout = captured
    try:
        spec = importlib.util.spec_from_file_location(
            "semantica_trace_mcp", os.path.join(SKILL_DIR, "mcp_server.py")
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    finally:
        sys.stdout = real_stdout
    return module, captured.getvalue()


@pytest.fixture(scope="module")
def mcp_module():
    module, stdout_at_import = _load_module()
    module._stdout_at_import = stdout_at_import  # 各テストから読めるようにしておく
    return module


def test_import_does_not_pollute_stdout(mcp_module):
    assert not mcp_module._stdout_at_import.strip(), (
        f"import polluted stdout: {mcp_module._stdout_at_import[:200]!r}"
    )


def test_semantica_import_is_deferred():
    """モジュールの import で semantica を読み込まない。

    読み込むと全セッションが起動時に実測5.6秒払う(stdio の MCP サーバーは
    セッション開始ごとに起動されるため)。この性質は「新しいプロセスの起動
    コスト」なので、共有プロセス内の ``mcp_module`` フィクスチャで検査すると、
    同じ pytest プロセス内で先に実行された他のテスト(test_idempotency.py 等、
    実データを渡すと semantica を import する)に汚染される。別プロセスを
    起こして検査することで、この汚染を避ける。
    """
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import importlib.util, sys, os; "
            "spec = importlib.util.spec_from_file_location("
            "'m', os.path.join(sys.argv[1], 'mcp_server.py')); "
            "m = importlib.util.module_from_spec(spec); "
            "spec.loader.exec_module(m); "
            "print('semantica.context' in sys.modules)",
            SKILL_DIR,
        ],
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, f"subprocess failed: {result.stderr[-500:]}"
    assert result.stdout.strip() == "False", (
        "semantica.context was imported at module import time "
        "(costs ~5.6s on every session start)"
    )


def test_invalid_direction_is_rejected(mcp_module):
    bad = mcp_module.causal_chain("whatever", "sideways")
    assert "error" in bad, "invalid direction was accepted"


def test_all_tools_are_present(mcp_module):
    tool_names = {"decisions_about_file", "sessions_touching_file", "causal_chain", "graph_stats"}
    missing = [t for t in tool_names if not callable(getattr(mcp_module, t, None))]
    assert not missing, f"missing tools: {missing}"


def test_path_forms_agree(mcp_module):
    """相対パス・絶対パス・`~` 付きパスが同じ結果を返す。

    不一致だと 0 件になり「触っていない」と誤読される。グラフが無い環境では
    判定できないので skip する。パスの一致だけを見るのが目的で、対象ファイルが
    実際にグラフへ記録されているかは問わないため、リポジトリ内の特定ファイルに
    依存せず一時ファイルで検査する。`~` 表記との等価性を試すため、一時ファイルは
    ホームディレクトリの下(``~/.cache``)に作る。
    """
    probe = mcp_module.graph_stats()
    if "error" in probe:
        pytest.skip("グラフがまだ無いためパス正規化の検査は行わない")

    home = os.path.expanduser("~")
    probe_dir = os.path.join(home, ".cache", "semantica-trace", "test-tmp")
    os.makedirs(probe_dir, exist_ok=True)
    target_file = os.path.join(probe_dir, "probe.txt")
    with open(target_file, "w") as f:
        f.write("probe")

    cwd = os.getcwd()
    os.chdir(probe_dir)
    try:
        a = mcp_module.decisions_about_file("probe.txt", limit=1)["file_path"]
        b = mcp_module.decisions_about_file(target_file, limit=1)["file_path"]
        c = mcp_module.decisions_about_file(
            os.path.join("~", os.path.relpath(target_file, home)), limit=1
        )["file_path"]
    finally:
        os.chdir(cwd)
        os.remove(target_file)

    assert a == b == c, f"path forms disagree: relative={a!r} absolute={b!r} tilde={c!r}"
