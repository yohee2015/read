import ctypes
import os
from ctypes import wintypes

from novel_reader import themes

user32 = ctypes.windll.user32

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_XDOWN = 0x0080
MOUSEEVENTF_XUP = 0x0100
MOUSEEVENTF_WHEEL = 0x0800
XBUTTON1 = 0x0001
XBUTTON2 = 0x0002
INPUT_MOUSE = 0
GA_ROOT = 2
GWLV_EXSTYLE = -20
WS_EX_TOPMOST = 0x0008
WS_EX_TOOLWINDOW = 0x0080

user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.GetWindowLongW.restype = ctypes.c_long
user32.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
user32.SetCursorPos.restype = wintypes.BOOL


def log(message):
    print(message, flush=True)
    path = os.environ.get("NOVEL_READER_SMOKE_OUT")
    if path:
        try:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(str(message) + "\n")
        except OSError:
            pass


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", wintypes.LONG), ("dy", wintypes.LONG),
        ("mouseData", wintypes.DWORD), ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD), ("dwExtraInfo", ctypes.c_void_p),
    ]


class _INPUTUNION(ctypes.Union):
    _fields_ = [("mi", MOUSEINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("union", _INPUTUNION)]


def send_mouse(flags, data=0, dx=0, dy=0):
    inp = INPUT()
    inp.type = INPUT_MOUSE
    inp.union.mi.dx = dx
    inp.union.mi.dy = dy
    inp.union.mi.mouseData = data
    inp.union.mi.dwFlags = flags
    user32.SendInput(1, ctypes.byref(inp), ctypes.sizeof(INPUT))


class SmokeRunner:
    def __init__(self, root, window, hotkeys, mouse, tray):
        self.root = root
        self.window = window
        self.hotkeys = hotkeys
        self.mouse = mouse
        self.tray = tray
        self.checks = {}
        self.failed = False
        self.done = False

    def start(self, delay=1500):
        self.checks = {
            "hotkeys_alive": self.hotkeys.is_alive(),
            "mouse_hook": self.mouse._hook is not None,
            "tray_window": self.tray._hwnd is not None,
            "chapters": len(self.window.chapters),
        }
        log("SMOKE-BEGIN %s" % self.checks)
        self.root.after(delay, self._sync_phase)
        self.root.after(25000, self._timeout)

    def _after(self, ms, fn):
        self.root.after(ms, fn)

    def _record(self, name, ok):
        self.checks[name] = bool(ok)
        if not ok:
            self.failed = True
        log("STEP %s %s" % (name, ok))

    def _guard(self, next_fn):
        def run():
            if self.done:
                return
            try:
                next_fn()
            except Exception as exc:
                self.checks["error"] = repr(exc)
                self.failed = True
                log("SMOKE-ERROR %r" % exc)
                self._finish()
        return run

    def _sync_phase(self):
        window = self.window
        try:
            window.cfg.set("theme.alpha", 0.65)
            window.apply_theme()
            self._record("alpha_applied",
                         abs(float(window.root.wm_attributes("-alpha")) - 0.65) < 1e-6)
            hwnd = user32.GetAncestor(int(window.root.winfo_id()), GA_ROOT)
            style = user32.GetWindowLongW(hwnd, GWLV_EXSTYLE)
            self._record(
                "toolwindow",
                bool(style & WS_EX_TOOLWINDOW)
                == bool(window.cfg.get("window.hide_taskbar", True)),
            )
            window.goto_chapter(0)
            self._record("nav_next", window.nav_chapter(1) and window.current == 1)
            window.goto_chapter(0)
            size_before = int(window.cfg.get("theme.font_size", 15))
            window.reader_zoom(1)
            self._record("zoom", int(window.cfg.get("theme.font_size", 15)) == size_before + 1)
            window.reader_zoom(-1)
            window.goto_chapter(0)
            window.reader.moveto(0.0)
            wheel_before = window.reader.frac()
            window.reader.text.event_generate("<MouseWheel>", delta=-120)
            window.root.update()
            self._record("wheel_normal", window.reader.frac() > wheel_before + 1e-6)
            window.set_pure(True)
            self._record("pure_on", window.pure)
            self._record("pure_alpha", abs(float(window.root.wm_attributes("-alpha")) - 1.0) < 1e-6)
            key_bg = str(window.reader.text.cget("bg"))
            self._record("key_auto", key_bg == themes.key_color_for(window.colors["fg"]))
            self._record("key_gap", themes.key_gap_ok(window.colors["fg"], key_bg))
            window.set_pure(False)
            self._record("pure_off", not window.pure)
            self._record("alpha_restored",
                         abs(float(window.root.wm_attributes("-alpha"))
                             - float(window.cfg.get("theme.alpha", 1.0))) < 1e-6)
            window.toggle_toc(False)
            window.toggle_toc(True)
            self._record("toc", window.toc_visible)
            window.jump_entry.delete(0, "end")
            window.jump_entry.insert(0, "2")
            window.do_jump()
            self._record("jump", window.current == 1)
            window.goto_chapter(0)
            window.hide_to_tray()
            self._record("hide", str(window.root.state()) == "withdrawn")
            window.show_window()
            self._record("show", str(window.root.state()) != "withdrawn")
            self._record("theme_menu", window._build_theme_menu() is not None)
            self._record("reader_menu", window._build_reader_menu() is not None)
            window.open_settings()
            dialog = window.settings_dialog
            self._record("settings_open", dialog is not None and dialog.winfo_exists())
            self._record("settings_apply", bool(dialog._apply()))
            dialog.destroy()
            window.settings_dialog = None
        except Exception as exc:
            self.checks["error"] = repr(exc)
            self.failed = True
            log("SMOKE-ERROR %r" % exc)
            self._finish()
            return
        self._after(400, self._guard(self._hotkey_phase))

    def _post_hotkey(self, hotkey_id):
        user32.PostThreadMessageW(self.hotkeys._tid, 0x0312, hotkey_id, 0)

    def _hotkey_phase(self):
        self._post_hotkey(1)
        self._after(400, self._guard(self._hotkey_hide_check))

    def _hotkey_hide_check(self):
        self._record("hotkey_hide", str(self.window.root.state()) == "withdrawn")
        self._post_hotkey(1)
        self._after(400, self._guard(self._hotkey_show_check))

    def _hotkey_show_check(self):
        self._record("hotkey_show", str(self.window.root.state()) != "withdrawn")
        self._after(200, self._guard(self._pure_input_phase))

    def _pure_input_phase(self):
        window = self.window
        try:
            window.goto_chapter(0)
            window.set_pure(True)
            window.root.update()
            hwnd = user32.GetAncestor(int(window.root.winfo_id()), GA_ROOT)
            if not hwnd:
                raise RuntimeError("no hwnd in pure mode")
            before = bool(window.cfg.get("window.topmost", False))
            window._toggle_topmost()
            window.root.update()
            style_on = user32.GetWindowLongW(hwnd, GWLV_EXSTYLE)
            self._record("topmost_on", bool(style_on & WS_EX_TOPMOST) != before)
            window._toggle_topmost()
            window.root.update()
            style_off = user32.GetWindowLongW(hwnd, GWLV_EXSTYLE)
            self._record("topmost_off", bool(style_off & WS_EX_TOPMOST) == before)
            rect = wintypes.RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            user32.SetCursorPos(
                (rect.left + rect.right) // 2, (rect.top + rect.bottom) // 2
            )
            frac0 = window.reader.frac()
            for _ in range(5):
                send_mouse(MOUSEEVENTF_WHEEL, (-120) & 0xFFFFFFFF)
            self._after(500, self._guard(lambda: self._pure_wheel_check(frac0)))
        except Exception as exc:
            self.checks["error"] = repr(exc)
            self.failed = True
            log("SMOKE-ERROR %r" % exc)
            self._finish()

    def _pure_wheel_check(self, frac0):
        self._record("wheel_pure", self.window.reader.frac() > frac0 + 1e-6)
        self.window.set_pure(False)
        self._after(300, self._guard(self._side_next_phase))

    def _inject_x(self, button, count=1):
        for _ in range(count):
            send_mouse(MOUSEEVENTF_XDOWN, button)
            send_mouse(MOUSEEVENTF_XUP, button)

    def _side_next_phase(self):
        self.mouse.side_global = True
        self.base = self.window.current
        self._inject_x(XBUTTON1)
        self._after(400, self._guard(self._side_next_check))

    def _side_next_check(self):
        self._record("side_next", self.window.current == self.base + 1)
        self._inject_x(XBUTTON2)
        self._after(400, self._guard(self._side_prev_check))

    def _side_prev_check(self):
        self._record("side_prev", self.window.current == self.base)
        self._after(200, self._guard(self._middle_phase))

    def _middle_phase(self):
        reader = self.window.reader
        scrollable = reader.text.yview()[1] - reader.text.yview()[0] < 0.999
        if not scrollable:
            self.checks["middle_drag"] = "skipped(not scrollable)"
            self._after(300, self._guard(self._finish))
            return
        self._original_active = self.mouse._our_active
        self.mouse._our_active = lambda: True
        reader.moveto(0.3)
        self.drag_start = reader.frac()
        send_mouse(MOUSEEVENTF_MIDDLEDOWN)
        for _ in range(4):
            send_mouse(MOUSEEVENTF_MOVE, 0, 0, 40)
        send_mouse(MOUSEEVENTF_MIDDLEUP)
        self._after(500, self._guard(self._middle_check))

    def _middle_check(self):
        if getattr(self, "_original_active", None) is not None:
            self.mouse._our_active = self._original_active
            self._original_active = None
        frac = self.window.reader.frac()
        self._record("middle_drag", frac < self.drag_start - 0.002)
        self._after(200, self._guard(self._finish))

    def _timeout(self):
        if self.done:
            return
        self.checks["error"] = "timeout"
        self.failed = True
        log("SMOKE-TIMEOUT %s" % self.checks)
        self._finish()

    def _finish(self):
        if self.done:
            return
        self.done = True
        self.mouse.side_global = bool(
            self.window.cfg.get("mouse.side_global", False)
        )
        if getattr(self, "_original_active", None) is not None:
            self.mouse._our_active = self._original_active
            self._original_active = None
        log("SMOKE %s %s" % (self.checks, "FAILED" if self.failed else "OK"))
        self.window.quit_app()
