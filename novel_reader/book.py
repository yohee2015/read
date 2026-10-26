import re
from dataclasses import dataclass

CHAPTER_LINE_MAX = 60
FALLBACK_CHUNK = 3000
TRAILING_PUNCT = "。！？；，、,.!?;"

HEAD_PATTERN = (
    r"第\s*[0-9０-９零〇一二三四五六七八九十百千万两]+\s*[章回节卷集部篇]"
    r"|(?:序章|楔子|引子|前言|内容简介|尾声|终章|完结|后记|番外\d*|外篇)"
    r"|(?:Chapter|CHAPTER|Ch\.)\s*\d+"
)
AUTO_CHAPTER_RE = re.compile(
    r"^\s*(?:" + HEAD_PATTERN + r")(?:\s*[:：]\s*|\s+)?[^\r\n]{0,40}?\s*$"
)
INT_RE = re.compile(r"^\d+$")
CHAPTER_NUM_RE = re.compile(
    r"第\s*([0-9０-９零〇一二三四五六七八九十百千万两]+)\s*[章回节卷集部篇]"
)
_CN_DIGIT = {
    "零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4,
    "五": 5, "六": 6, "七": 7, "八": 8, "九": 9,
}
_CN_UNIT = {"十": 10, "百": 100, "千": 1000}


@dataclass
class Chapter:
    index: int
    title: str
    body: str


def decode_bytes(data):
    if data.startswith(b"\xef\xbb\xbf"):
        return data.decode("utf-8-sig", errors="replace")
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return data.decode("utf-16", errors="replace")
    for encoding in ("utf-8", "gb18030", "gbk", "big5", "latin-1"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def load_text(path):
    with open(path, "rb") as fh:
        return decode_bytes(fh.read())


def cn_to_int(text):
    if not text:
        return None
    text = text.strip()
    if INT_RE.match(text):
        return int(text)
    if all(ch in "０１２３４５６７８９" for ch in text):
        return int(text.translate(str.maketrans("０１２３４５６７８９", "0123456789")))
    total = section = number = 0
    for ch in text:
        if ch in _CN_DIGIT:
            number = _CN_DIGIT[ch]
        elif ch in _CN_UNIT:
            section += (number or 1) * _CN_UNIT[ch]
            number = 0
        elif ch == "万":
            total += (section + number) * 10000
            section = number = 0
        else:
            return None
    return total + section + number


def _is_header_line(stripped):
    if not stripped or len(stripped) > CHAPTER_LINE_MAX:
        return False
    if stripped[-1] in TRAILING_PUNCT:
        return False
    return bool(AUTO_CHAPTER_RE.match(stripped))


def split_by_regex(text, pattern, use_auto_filter=False):
    compiled = re.compile(pattern)
    lines = text.splitlines()
    marks = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if use_auto_filter:
            ok = _is_header_line(stripped)
        else:
            ok = bool(stripped) and len(stripped) <= CHAPTER_LINE_MAX and bool(
                compiled.search(stripped)
            )
        if ok:
            marks.append((i, stripped))
    if not marks:
        return [], 0
    chapters = []
    if marks[0][0] > 0:
        preamble = "\n".join(lines[: marks[0][0]]).strip()
        if len(preamble) > 80:
            chapters.append(Chapter(0, "前文", preamble))
    for pos, (line_no, title) in enumerate(marks):
        end = marks[pos + 1][0] if pos + 1 < len(marks) else len(lines)
        body = "\n".join(lines[line_no:end]).strip("\n")
        chapters.append(Chapter(len(chapters), title, body))
    return [c for c in chapters if c.body.strip()], len(marks)


def split_by_size(text):
    paragraphs = [p for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks = []
    buf = []
    size = 0
    for para in paragraphs:
        buf.append(para)
        size += len(para)
        if size >= FALLBACK_CHUNK:
            chunks.append("\n\n".join(buf))
            buf, size = [], 0
    if buf:
        chunks.append("\n\n".join(buf))
    if not chunks and text.strip():
        chunks = [text.strip()]
    return [Chapter(i, "第%d节" % (i + 1), chunk) for i, chunk in enumerate(chunks)]


def split_chapters(text, custom_pattern=None):
    if custom_pattern:
        try:
            chapters, count = split_by_regex(text, custom_pattern)
        except re.error:
            chapters, count = [], 0
        if count >= 1:
            return chapters, "custom", None
        return split_by_size(text), "fallback", "自定义正则未匹配到章节，已按字数分节"
    chapters, count = split_by_regex(text, "", use_auto_filter=True)
    if count >= 1:
        return chapters, "auto", None
    return split_by_size(text), "fallback", "未识别到章节标题，已按字数分节（可在设置中填写自定义正则）"


def resolve_jump(query, chapters, current=0):
    if not chapters:
        return None
    query = (query or "").strip()
    if not query:
        return None
    if INT_RE.match(query):
        idx = int(query) - 1
        return idx if 0 <= idx < len(chapters) else None
    matched = CHAPTER_NUM_RE.search(query)
    if matched:
        number = cn_to_int(matched.group(1))
        if number is not None:
            idx = number - 1
            if 0 <= idx < len(chapters):
                return idx
    lowered = query.lower()
    for offset in range(len(chapters)):
        idx = (current + offset) % len(chapters)
        if lowered in chapters[idx].title.lower():
            return idx
    return None


def load_book(path, custom_pattern=None):
    text = load_text(path)
    chapters, mode, note = split_chapters(text, custom_pattern)
    return chapters, mode, note
