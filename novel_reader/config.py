import copy
import json
import os
import threading

APP_DIR = os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "NovelReader")
CONFIG_PATH = os.environ.get("NOVEL_READER_CONFIG") or os.path.join(APP_DIR, "config.json")

DEFAULTS = {
    "theme": {
        "preset": "dark",
        "bg": "#1e1e1e",
        "fg": "#d4d4d4",
        "font_family": "微软雅黑",
        "font_size": 15,
        "line_spacing": 1.6,
        "alpha": 1.0,
        "key_color": "",
    },
    "hotkeys": {
        "hide": "ctrl+alt+h",
        "transparent": "ctrl+alt+t",
        "next": "ctrl+alt+n",
        "prev": "ctrl+alt+p",
    },
    "mouse": {
        "enabled": True,
        "side_buttons": True,
        "side_global": False,
        "middle_menu": True,
        "middle_threshold": 40,
        "long_press_ms": 800,
    },
    "window": {
        "geometry": "980x680+120+80",
        "topmost": True,
        "toc_visible": True,
        "close_to_tray": True,
        "hide_taskbar": True,
    },
    "reader": {
        "last_book": "",
        "progress": {},
    },
    "chapter_regex": "",
}


def _merge(dst, src):
    for key, value in src.items():
        if isinstance(value, dict) and isinstance(dst.get(key), dict):
            _merge(dst[key], value)
        else:
            dst[key] = copy.deepcopy(value)


class Config:
    def __init__(self, path=CONFIG_PATH):
        self.path = path
        self._lock = threading.Lock()
        self.data = copy.deepcopy(DEFAULTS)
        self.load()

    def load(self):
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                loaded = json.load(fh)
        except (OSError, ValueError):
            return
        if isinstance(loaded, dict):
            _merge(self.data, loaded)

    def save(self):
        with self._lock:
            try:
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                tmp = self.path + ".tmp"
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(self.data, fh, ensure_ascii=False, indent=2)
                os.replace(tmp, self.path)
            except OSError:
                pass

    def get(self, dotted, default=None):
        node = self.data
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, dotted, value, save=False):
        parts = dotted.split(".")
        node = self.data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
        if save:
            self.save()

    def remember_progress(self, path, chapter_index, scroll):
        progress = self.data["reader"].setdefault("progress", {})
        progress[path] = {"chapter": chapter_index, "scroll": scroll}
        if len(progress) > 30:
            for old in sorted(progress, key=lambda k: k)[: len(progress) - 30]:
                progress.pop(old, None)
        self.data["reader"]["last_book"] = path
