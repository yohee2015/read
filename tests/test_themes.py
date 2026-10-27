import unittest

from novel_reader import themes


class KeyColorTests(unittest.TestCase):
    def test_differs_from_fg(self):
        for fg in ("#d4d4d4", "#222222", "#ffffff", "#000000", "#c7edcc"):
            key = themes.key_color_for(fg)
            self.assertNotEqual(key, fg)
            self.assertRegex(key, r"^#[0-9a-f]{6}$")

    def test_safe_gap_distance(self):
        fg = (0x50, 0x60, 0x70)
        key = themes.hex_to_rgb(themes.key_color_for("#506070"))
        for i in range(3):
            self.assertGreaterEqual(abs(key[i] - fg[i]), themes.KEY_SAFE_GAP)

    def test_near_fg(self):
        key = themes.hex_to_rgb(themes.key_color_for("#d4d4d4"))
        fg = (0xD4, 0xD4, 0xD4)
        for i in range(3):
            self.assertLessEqual(abs(key[i] - fg[i]), themes.KEY_SAFE_GAP)

    def test_no_overflow(self):
        self.assertEqual(themes.key_color_for("#ffffff"), "#e7e7e7")
        self.assertEqual(themes.key_color_for("#000000"), "#181818")

    def test_legacy_auto_key_rejected(self):
        self.assertFalse(themes.key_gap_ok("#000000", "#010101"))
        self.assertFalse(themes.key_gap_ok("#d4d4d4", "#d3d3d3"))
        self.assertTrue(themes.key_gap_ok("#000000", themes.key_color_for("#000000")))

    def test_invalid_key_rejected(self):
        self.assertFalse(themes.key_gap_ok("#d4d4d4", ""))
        self.assertFalse(themes.key_gap_ok("#d4d4d4", "#xyzxyz"))
        self.assertFalse(themes.key_gap_ok("#d4d4d4", "#d4d4"))


if __name__ == "__main__":
    unittest.main()
