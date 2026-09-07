"""index_freshness フックの通知ロジック（純粋関数）のテスト。"""

import importlib.util
import os
import unittest

_SCRIPT = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "scripts",
    "index_freshness.py",
)
_spec = importlib.util.spec_from_file_location("index_freshness", _SCRIPT)
index_freshness = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(index_freshness)


class BuildNoticeTest(unittest.TestCase):
    def test_missing_index_prompts_setup(self) -> None:
        notice = index_freshness.build_notice({"missing_index": True, "stale": 0})
        self.assertIsNotNone(notice)
        self.assertIn("未構築", notice)

    def test_stale_index_prompts_update(self) -> None:
        notice = index_freshness.build_notice(
            {"missing_index": False, "indexed": True, "stale": 3}
        )
        self.assertIsNotNone(notice)
        self.assertIn("3", notice)

    def test_up_to_date_emits_nothing(self) -> None:
        notice = index_freshness.build_notice(
            {"missing_index": False, "indexed": True, "stale": 0}
        )
        self.assertIsNone(notice)


if __name__ == "__main__":
    unittest.main()
