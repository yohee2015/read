import unittest

from novel_reader import themes


class KeyColorTests(unittest.TestCase):
    def test_differs_from_fg(self):
        for fg in ("#d4d4d4", "#222222", "#ffffff", "#000000", "#c7edcc"):
            key = themes.key_color_for(fg)
            self.assertNotEqual(key, fg)
            self.assertRegex(key, r"^#[0-9a-f]{6}$")

    def test_delta_distance(self):
        fg = (0x50, 0x60, 0x70)
        key = themes.hex_to_rgb(themes.key_color_for("#506070"))
        for i in range(3):
            self.assertGreaterEqual(abs(key[i] - fg[i]), 1)

    def test_near_fg(self):
        key = themes.hex_to_rgb(themes.key_color_for("#d4d4d4"))
        fg = (0xD4, 0xD4, 0xD4)
        for i in range(3):
            self.assertLessEqual(abs(key[i] - fg[i]), themes.KEY_DELTA)

    def test_no_overflow(self):
        self.assertEqual(themes.key_color_for("#ffffff"), "#fefefe")
        self.assertEqual(themes.key_color_for("#000000"), "#010101")


if __name__ == "__main__":
    unittest.main()
