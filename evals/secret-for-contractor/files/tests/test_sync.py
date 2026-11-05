import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import tempfile

from sync import load_settings


class LoadSettings(unittest.TestCase):
    def test_a_value_may_hold_an_equals_sign(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "settings"
            path.write_text("# comment\nPAY_ENDPOINT=https://x.example/v2?region=eu\nSYNC_TIMEOUT_SECONDS=30\n", encoding="utf-8")
            settings = load_settings(path)
        self.assertEqual(settings["PAY_ENDPOINT"], "https://x.example/v2?region=eu")
        self.assertEqual(settings["SYNC_TIMEOUT_SECONDS"], "30")


if __name__ == "__main__":
    unittest.main()
