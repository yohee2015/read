PRESETS = {
    "white": {"label": "素白", "bg": "#ffffff", "fg": "#222222", "accent": "#2f6fb2"},
    "dark": {"label": "暗夜", "bg": "#1e1e1e", "fg": "#d4d4d4", "accent": "#4a90d9"},
    "eye": {"label": "护眼", "bg": "#c7edcc", "fg": "#2b4a2f", "accent": "#2f7d4f"},
    "paper": {"label": "羊皮纸", "bg": "#f3e7d3", "fg": "#4a3b28", "accent": "#8a6d3b"},
}


def hex_to_rgb(value):
    value = value.lstrip("#")
    if len(value) == 3:
        value = "".join(ch * 2 for ch in value)
    try:
        return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (0, 0, 0)


def is_dark(color):
    r, g, b = hex_to_rgb(color)
    return (r * 299 + g * 587 + b * 114) / 1000 < 128


def derive_colors(bg, fg=None, accent=None):
    dark = is_dark(bg)
    if fg is None:
        fg = "#e8e8e8" if dark else "#222222"
    if accent is None:
        accent = "#4a90d9" if dark else "#2f6fb2"
    hint = "#8f8f8f" if dark else "#7a7a7a"
    edge = "#3a3a3a" if dark else "#dcdcdc"
    return {"bg": bg, "fg": fg, "accent": accent, "hint": hint, "edge": edge}


KEY_SAFE_GAP = 24


def key_color_for(fg, gap=KEY_SAFE_GAP):
    r, g, b = hex_to_rgb(fg)
    gap = max(1, min(127, int(gap)))

    def shift(v):
        return v - gap if v > 255 - gap else v + gap

    return "#%02x%02x%02x" % (shift(r), shift(g), shift(b))


def key_gap_ok(fg, key, gap=KEY_SAFE_GAP):
    if not isinstance(key, str):
        return False
    value = key.strip().lower()
    digits = value[1:] if value.startswith("#") else ""
    if len(digits) not in (3, 6):
        return False
    if any(ch not in "0123456789abcdef" for ch in digits):
        return False
    fg_rgb = hex_to_rgb(fg)
    key_rgb = hex_to_rgb(value)
    return all(abs(a - b) >= gap for a, b in zip(fg_rgb, key_rgb))


def spacing_pixels(font_size, line_spacing):
    return max(0, int(round(font_size * (line_spacing - 1))))
