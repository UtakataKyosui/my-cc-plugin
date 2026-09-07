#!/usr/bin/env python3
"""check-test-exists.py のユニットテスト（stdlib unittest のみ・pytest 不要）

実行方法:
    python3 test_check-test-exists.py

ソースファイル名にハイフンが含まれるため、importlib で直接ロードする。
"""

import importlib.util
import os
import unittest

# ハイフン入りファイル名を module としてロードする
_HERE = os.path.dirname(os.path.abspath(__file__))
_SOURCE_PATH = os.path.join(_HERE, "check-test-exists.py")
_spec = importlib.util.spec_from_file_location("check_test_exists", _SOURCE_PATH)
if _spec is None or _spec.loader is None:
    raise RuntimeError(f"cannot load module from {_SOURCE_PATH}")
cte = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cte)


class IsExcludedFileTest(unittest.TestCase):
    def test_markdown_is_excluded(self):
        self.assertTrue(cte.is_excluded_file("/proj/src/README.md"))

    def test_json_is_excluded(self):
        self.assertTrue(cte.is_excluded_file("/proj/config/settings.json"))

    def test_barrel_index_ts_is_excluded(self):
        self.assertTrue(cte.is_excluded_file("/proj/src/index.ts"))

    def test_init_py_is_excluded(self):
        self.assertTrue(cte.is_excluded_file("/proj/pkg/__init__.py"))

    def test_claude_config_dir_is_excluded(self):
        # NEW: ~/.claude/ 配下はプロジェクトソースではないため除外する
        claude_path = os.path.join(
            os.path.expanduser("~/.claude/"), "hooks", "scripts", "foo.py"
        )
        self.assertTrue(cte.is_excluded_file(claude_path))

    def test_claude_config_dir_relative_segment_is_excluded(self):
        # NEW: パス中に /.claude/ を含む場合も除外する
        self.assertTrue(cte.is_excluded_file("/anywhere/.claude/skills/foo/bar.py"))

    def test_ordinary_source_is_not_excluded(self):
        self.assertFalse(cte.is_excluded_file("/proj/src/parser.py"))


class IsTestFileTest(unittest.TestCase):
    def test_python_test_prefix(self):
        self.assertTrue(cte.is_test_file("/proj/tests/test_x.py"))

    def test_typescript_dot_test(self):
        self.assertTrue(cte.is_test_file("/proj/src/x.test.ts"))

    def test_non_test_source(self):
        self.assertFalse(cte.is_test_file("/proj/src/x.py"))


class TddEnforceGateTest(unittest.TestCase):
    """NEW: _is_tdd_enforce_enabled() のゲート判定（DEFAULT DISABLED）"""

    def setUp(self):
        # 環境変数とモジュール設定を退避し、各テストでクリーンな状態を作る
        self._saved_env = os.environ.get("TDD_ENFORCE_ENABLED")
        if "TDD_ENFORCE_ENABLED" in os.environ:
            del os.environ["TDD_ENFORCE_ENABLED"]
        self._saved_settings = cte._SETTINGS

    def tearDown(self):
        if self._saved_env is None:
            os.environ.pop("TDD_ENFORCE_ENABLED", None)
        else:
            os.environ["TDD_ENFORCE_ENABLED"] = self._saved_env
        cte._SETTINGS = self._saved_settings

    def test_disabled_by_default(self):
        cte._SETTINGS = {}
        self.assertFalse(cte._is_tdd_enforce_enabled())

    def test_enabled_via_env_truthy(self):
        cte._SETTINGS = {}
        for val in ("1", "true", "yes", "on", "TRUE", "On"):
            os.environ["TDD_ENFORCE_ENABLED"] = val
            self.assertTrue(cte._is_tdd_enforce_enabled(), f"env={val!r} should enable")

    def test_not_enabled_via_env_falsy(self):
        cte._SETTINGS = {}
        for val in ("0", "false", "no", "off", ""):
            os.environ["TDD_ENFORCE_ENABLED"] = val
            self.assertFalse(
                cte._is_tdd_enforce_enabled(), f"env={val!r} should NOT enable"
            )

    def test_enabled_via_settings(self):
        os.environ.pop("TDD_ENFORCE_ENABLED", None)
        cte._SETTINGS = {"tddEnforce": {"enabled": True}}
        self.assertTrue(cte._is_tdd_enforce_enabled())

    def test_settings_enabled_false_keeps_disabled(self):
        os.environ.pop("TDD_ENFORCE_ENABLED", None)
        cte._SETTINGS = {"tddEnforce": {"enabled": False}}
        self.assertFalse(cte._is_tdd_enforce_enabled())


if __name__ == "__main__":
    unittest.main(verbosity=2)
