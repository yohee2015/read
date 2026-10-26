import ctypes
import threading
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

user32.RegisterHotKey.argtypes = [
    wintypes.HWND, ctypes.c_int, ctypes.c_uint, ctypes.c_uint
]
user32.RegisterHotKey.restype = wintypes.BOOL
user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
user32.UnregisterHotKey.restype = wintypes.BOOL
user32.GetMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG), wintypes.HWND, ctypes.c_uint, ctypes.c_uint
]
user32.GetMessageW.restype = ctypes.c_int
user32.PostThreadMessageW.argtypes = [
    wintypes.DWORD, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM
]
user32.PostThreadMessageW.restype = wintypes.BOOL

WM_HOTKEY = 0x0312
WM_QUIT_MSG = 0x0012
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000
WM_APP = 0x8000
WM_REBIND = WM_APP + 10

LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)

MOD_KEYS = {
    "ctrl": MOD_CONTROL, "control": MOD_CONTROL,
    "alt": MOD_ALT, "shift": MOD_SHIFT,
    "win": MOD_WIN, "super": MOD_WIN, "cmd": MOD_WIN,
}
NAMED_KEYS = {
    "esc": 0x1B, "escape": 0x1B, "space": 0x20, "tab": 0x09,
    "enter": 0x0D, "return": 0x0D, "backspace": 0x08, "insert": 0x2D,
    "delete": 0x2E, "home": 0x24, "end": 0x23,
    "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
    "pageup": 0x21, "pagedown": 0x22, "prior": 0x21, "next": 0x22,
    "pause": 0x13, "scrolllock": 0x91, "numlock": 0x90, "printscreen": 0x2C,
}


def parse_combo(combo):
    parts = [p.strip().lower() for p in (combo or "").split("+") if p.strip()]
    if len(parts) < 2:
        raise ValueError("快捷键必须包含修饰键，例如 ctrl+alt+h")
    *modifiers, key = parts
    mods = 0
    for name in modifiers:
        if name not in MOD_KEYS:
            raise ValueError("未知修饰键: %s" % name)
        mods |= MOD_KEYS[name]
    if key.startswith("f") and key[1:].isdigit():
        number = int(key[1:])
        if not 1 <= number <= 24:
            raise ValueError("功能键范围为 F1-F24")
        vk = 0x70 + number - 1
    elif len(key) == 1 and (key.isalnum()):
        vk = ord(key.upper())
    elif key in NAMED_KEYS:
        vk = NAMED_KEYS[key]
    else:
        raise ValueError("不支持的按键: %s（可用字母/数字/F1-F12/方向键等）" % key)
    return mods | MOD_NOREPEAT, vk


class HotkeyThread(threading.Thread):
    daemon = True

    def __init__(self, emit):
        super().__init__(name="hotkeys")
        self.emit = emit
        self._mapping = {}
        self._registered = []
        self._tid = None
        self._ready = threading.Event()

    def set_mapping(self, mapping):
        self._mapping = dict(mapping)
        if self._tid:
            user32.PostThreadMessageW(self._tid, WM_REBIND, 0, 0)

    def stop(self):
        if self._tid:
            user32.PostThreadMessageW(self._tid, WM_QUIT_MSG, 0, 0)

    def wait_ready(self, timeout=3):
        self._ready.wait(timeout)

    def _clear(self):
        for hot_id in self._registered:
            user32.UnregisterHotKey(None, hot_id)
        self._registered = []

    def _apply(self):
        self._clear()
        errors = []
        for hot_id, (name, combo) in enumerate(self._mapping.items(), start=1):
            if not combo:
                continue
            try:
                mods, vk = parse_combo(combo)
            except ValueError as exc:
                errors.append("%s: %s" % (name, exc))
                continue
            if not user32.RegisterHotKey(None, hot_id, mods, vk):
                errors.append("%s: %s 已被其它程序占用" % (name, combo))
                continue
            self._registered.append(hot_id)
        for message in errors:
            self.emit("hotkey_error", message)

    def run(self):
        self._tid = kernel32.GetCurrentThreadId()
        self._apply()
        self._ready.set()
        msg = wintypes.MSG()
        while True:
            result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result in (0, -1):
                break
            if msg.message == WM_REBIND:
                self._apply()
            elif msg.message == WM_HOTKEY:
                hot_id = int(msg.wParam)
                names = list(self._mapping)
                if 1 <= hot_id <= len(names):
                    self.emit("hotkey", names[hot_id - 1])
        self._clear()
