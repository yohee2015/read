import json
import os
import tempfile
import unittest

from novel_reader.config import DEFAULTS, Config


class ConfigLoadTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "config.json")

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, data):
        with open(self.path, "w", encoding="utf-8") as fh:
            json.dump(data, fh, ensure_ascii=False)

    def test_scalar_values_override_defaults(self):
        self._write({
            "theme": {"font_size": 22, "bg": "#101010"},
            "window": {"geometry": "640x480+10+20", "topmost": False},
            "reader": {
                "last_book": "D:\\books\\a.txt",
                "progress": {"D:\\books\\a.txt": {"chapter": 3, "scroll": 0.5}},
            },
        })
        cfg = Config(self.path)
        self.assertEqual(cfg.get("theme.font_size"), 22)
        self.assertEqual(cfg.get("theme.bg"), "#101010")
        self.assertEqual(cfg.get("window.geometry"), "640x480+10+20")
        self.assertIs(cfg.get("window.topmost"), False)
        self.assertEqual(cfg.get("reader.last_book"), "D:\\books\\a.txt")
        self.assertEqual(
            cfg.get("reader.progress")["D:\\books\\a.txt"],
            {"chapter": 3, "scroll": 0.5},
        )

    def test_missing_keys_fall_back_to_defaults(self):
        self._write({"theme": {"font_size": 22}})
        cfg = Config(self.path)
        self.assertEqual(cfg.get("theme.font_size"), 22)
        self.assertEqual(cfg.get("theme.line_spacing"), DEFAULTS["theme"]["line_spacing"])
        self.assertEqual(cfg.get("window.geometry"), DEFAULTS["window"]["geometry"])

    def test_hide_taskbar_default_and_override(self):
        self.assertIs(Config(self.path).get("window.hide_taskbar"), True)
        self._write({"window": {"hide_taskbar": False}})
        self.assertIs(Config(self.path).get("window.hide_taskbar"), False)

    def test_appearance_and_hide_hotkey_defaults(self):
        cfg = Config(self.path)
        self.assertEqual(cfg.get("theme.font_family"), "宋体")
        self.assertEqual(cfg.get("theme.font_size"), 13)
        self.assertEqual(cfg.get("theme.line_spacing"), 1.0)
        self.assertEqual(cfg.get("hotkeys.hide"), "ctrl+alt+z")

    def test_corrupt_file_uses_defaults(self):
        with open(self.path, "w", encoding="utf-8") as fh:
            fh.write("{not json")
        cfg = Config(self.path)
        self.assertEqual(cfg.get("theme.font_size"), DEFAULTS["theme"]["font_size"])


class ProgressTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = os.path.join(self.tmp.name, "config.json")
        self.cfg = Config(self.path)

    def tearDown(self):
        self.tmp.cleanup()

    def test_remember_progress_sets_last_book(self):
        self.cfg.remember_progress("D:\\books\\a.txt", 4, 0.25)
        self.assertEqual(self.cfg.get("reader.last_book"), "D:\\books\\a.txt")
        self.assertEqual(
            self.cfg.get("reader.progress")["D:\\books\\a.txt"],
            {"chapter": 4, "scroll": 0.25},
        )

    def test_progress_limited_to_thirty_books(self):
        for i in range(35):
            self.cfg.remember_progress("book%02d" % i, i, 0.0)
        self.assertEqual(len(self.cfg.get("reader.progress")), 30)


if __name__ == "__main__":
    unittest.main()
