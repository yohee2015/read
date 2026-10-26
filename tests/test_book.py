import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from novel_reader import book

SAMPLE = """书籍简介

第1章 起点
这是第一章的内容。

第2章 发展
第二章的内容，很长很长。

第三章 高潮
第三章的内容。

第4章 结局
大结局。
"""


class SplitTests(unittest.TestCase):
    def test_auto_split(self):
        chapters, mode, note = book.split_chapters(SAMPLE)
        self.assertEqual(mode, "auto")
        self.assertIsNone(note)
        self.assertEqual(len(chapters), 4)
        self.assertEqual(chapters[0].title, "第1章 起点")
        self.assertIn("第一章的内容", chapters[0].body)
        self.assertIn("第4章 结局", chapters[3].body)
        self.assertEqual(chapters[1].index, 1)

    def test_preamble_kept(self):
        chapters, _, _ = book.split_chapters(SAMPLE)
        self.assertEqual(chapters[0].title, "第1章 起点")

    def test_preamble_long_kept(self):
        text = "简介" * 100 + "\n\n第1章 A\n内容"
        chapters, mode, _ = book.split_chapters(text)
        self.assertEqual(mode, "auto")
        self.assertEqual(chapters[0].title, "前文")
        self.assertEqual(chapters[1].title, "第1章 A")

    def test_fallback_when_no_headers(self):
        text = "hello world\n\nmore text here"
        chapters, mode, note = book.split_chapters(text)
        self.assertEqual(mode, "fallback")
        self.assertIsNotNone(note)
        self.assertGreaterEqual(len(chapters), 1)

    def test_fallback_by_size(self):
        text = "\n\n".join(["段落" * 100] * 20)
        chapters, mode, _ = book.split_chapters(text)
        self.assertEqual(mode, "fallback")
        self.assertGreater(len(chapters), 1)

    def test_custom_pattern(self):
        chapters, mode, _ = book.split_chapters(SAMPLE, r"^第\d+章")
        self.assertEqual(mode, "custom")
        self.assertEqual(
            [c.title for c in chapters], ["第1章 起点", "第2章 发展", "第4章 结局"]
        )

    def test_custom_pattern_no_match(self):
        chapters, mode, note = book.split_chapters(SAMPLE, r"^不存在的前缀")
        self.assertEqual(mode, "fallback")
        self.assertIsNotNone(note)

    def test_custom_pattern_invalid(self):
        chapters, mode, note = book.split_chapters(SAMPLE, "[invalid")
        self.assertEqual(mode, "fallback")
        self.assertIsNotNone(note)

    def test_chinese_numeral_headers(self):
        text = "第一回 开始\n内容\n第百零二章 后来\n内容"
        chapters, mode, _ = book.split_chapters(text)
        self.assertEqual(mode, "auto")
        self.assertEqual(len(chapters), 2)
        self.assertEqual(chapters[1].title, "第百零二章 后来")

    def test_long_line_not_header(self):
        text = "第1章 " + "很" * 80 + "\n\n第2章 B\n内容"
        chapters, mode, _ = book.split_chapters(text)
        self.assertEqual(mode, "auto")
        self.assertEqual([c.title for c in chapters], ["前文", "第2章 B"])

    def test_body_line_starting_with_chapter_not_header(self):
        text = "第1章 A\n第2章的内容，很长很长。\n真正的第二章在这里\n第2章 B\n内容"
        chapters, mode, _ = book.split_chapters(text)
        self.assertEqual(mode, "auto")
        self.assertEqual([c.title for c in chapters], ["第1章 A", "第2章 B"])

    def test_english_chapter(self):
        text = "Chapter 1 Hello\n内容\nChapter 2 World\n内容"
        chapters, mode, _ = book.split_chapters(text)
        self.assertEqual(mode, "auto")
        self.assertEqual(len(chapters), 2)


class JumpTests(unittest.TestCase):
    def setUp(self):
        self.chapters, _, _ = book.split_chapters(SAMPLE)

    def test_jump_by_number(self):
        self.assertEqual(book.resolve_jump("3", self.chapters), 2)
        self.assertEqual(book.resolve_jump("第2章", self.chapters), 1)
        self.assertEqual(book.resolve_jump("第二章", self.chapters), 1)

    def test_jump_out_of_range(self):
        self.assertIsNone(book.resolve_jump("99", self.chapters))
        self.assertIsNone(book.resolve_jump("", self.chapters))

    def test_jump_by_keyword(self):
        self.assertEqual(book.resolve_jump("结局", self.chapters), 3)


class DecodeTests(unittest.TestCase):
    def test_utf8(self):
        self.assertEqual(book.decode_bytes("中文".encode("utf-8")), "中文")

    def test_utf8_bom(self):
        self.assertEqual(book.decode_bytes(b"\xef\xbb\xbf" + "中文".encode("utf-8")), "中文")

    def test_gb18030(self):
        self.assertEqual(book.decode_bytes("中文测试".encode("gb18030")), "中文测试")

    def test_utf16(self):
        self.assertEqual(book.decode_bytes("中文".encode("utf-16")), "中文")

    def test_load_text_roundtrip(self):
        with tempfile.NamedTemporaryFile("wb", suffix=".txt", delete=False) as fh:
            fh.write("第1章 A\n内容".encode("gb18030"))
            path = fh.name
        try:
            self.assertIn("第1章", book.load_text(path))
        finally:
            os.unlink(path)


if __name__ == "__main__":
    unittest.main()
