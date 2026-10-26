import ctypes
import os
import threading
import time
from ctypes import wintypes

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32
kernel32.GetModuleHandleW.restype = wintypes.HMODULE
kernel32.GetCurrentThreadId.restype = wintypes.DWORD

WH_MOUSE_LL = 14
WM_MOUSEMOVE = 0x0200
WM_MBUTTONDOWN = 0x0207
WM_MBUTTONUP = 0x0208
WM_MOUSEWHEEL = 0x020A
WM_XBUTTONDOWN = 0x020B
XBUTTON1 = 1
XBUTTON2 = 2
WM_QUIT = 0x0012
VK_CONTROL = 0x11

LRESULT = ctypes.c_ssize_t
HOOKPROC = ctypes.WINFUNCTYPE(LRESULT, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)


class MSLLHOOKSTRUCT(ctypes.Structure):
    _fields_ = [
        ("pt", wintypes.POINT),
        ("mouseData", wintypes.DWORD),
        ("flags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ctypes.c_void_p),
    ]


LPMSLLHOOKSTRUCT = ctypes.POINTER(MSLLHOOKSTRUCT)

user32.SetWindowsHookExW.argtypes = [
    ctypes.c_int, HOOKPROC, wintypes.HINSTANCE, wintypes.DWORD
]
user32.SetWindowsHookExW.restype = wintypes.HHOOK
user32.CallNextHookEx.argtypes = [
    wintypes.HHOOK, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM
]
user32.CallNextHookEx.restype = LRESULT
user32.UnhookWindowsHookEx.argtypes = [wintypes.HHOOK]
user32.UnhookWindowsHookEx.restype = wintypes.BOOL
user32.GetForegroundWindow.restype = wintypes.HWND
user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
user32.GetWindowThreadProcessId.restype = wintypes.DWORD
user32.GetMessageW.argtypes = [
    ctypes.POINTER(wintypes.MSG), wintypes.HWND, ctypes.c_uint, ctypes.c_uint
]
user32.GetMessageW.restype = ctypes.c_int
user32.PostThreadMessageW.argtypes = [
    wintypes.DWORD, ctypes.c_uint, wintypes.WPARAM, wintypes.LPARAM
]
user32.PostThreadMessageW.restype = wintypes.BOOL
user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
user32.GetWindowRect.restype = wintypes.BOOL
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.IsWindowVisible.restype = wintypes.BOOL
user32.GetAsyncKeyState.argtypes = [ctypes.c_int]
user32.GetAsyncKeyState.restype = ctypes.c_short


class MouseHook(threading.Thread):
    daemon = True

    def __init__(self, emit):
        super().__init__(name="mouse-hook")
        self.emit = emit
        self.enabled = True
        self.side_enabled = True
        self.side_global = False
        self.middle_menu = True
        self.middle_threshold = 40
        self.long_press_ms = 800
        self._proc = HOOKPROC(self._proc_fn)
        self._hook = None
        self._tid = None
        self._ready = threading.Event()
        self._mid_down = False
        self._mid_start = (0, 0)
        self._mid_last = (0, 0)
        self._mid_moved = 0.0
        self._mid_armed = False
        self._menu_fired = False
        self._press_time = 0.0
        self._generation = 0
        self._pid = os.getpid()
        self.wheel_capture = False
        self.wheel_hwnd = 0

    def apply_config(self, cfg):
        self.enabled = bool(cfg.get("mouse.enabled", True))
        self.side_enabled = bool(cfg.get("mouse.side_buttons", True))
        self.side_global = bool(cfg.get("mouse.side_global", False))
        self.middle_menu = bool(cfg.get("mouse.middle_menu", True))
        self.middle_threshold = int(cfg.get("mouse.middle_threshold", 40))
        self.long_press_ms = int(cfg.get("mouse.long_press_ms", 800))

    def stop(self):
        if self._tid:
            user32.PostThreadMessageW(self._tid, WM_QUIT, 0, 0)

    def wait_ready(self, timeout=3):
        self._ready.wait(timeout)

    def _our_active(self):
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return False
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value == self._pid

    def _proc_fn(self, n_code, w_param, l_param):
        try:
            if n_code >= 0 and self._handle(int(w_param), int(l_param)):
                return 1
        except Exception:
            pass
        return user32.CallNextHookEx(self._hook, n_code, w_param, l_param)

    def _handle(self, msg, l_param):
        data = ctypes.cast(ctypes.c_void_p(l_param), LPMSLLHOOKSTRUCT).contents
        x = int(data.pt.x)
        y = int(data.pt.y)
        if msg == WM_MOUSEWHEEL and self.wheel_capture:
            if self._over_wheel_rect(x, y):
                delta = ctypes.c_short((int(data.mouseData) >> 16) & 0xFFFF).value
                if delta:
                    ctrl = (user32.GetAsyncKeyState(VK_CONTROL) & 0x8000) != 0
                    self.emit("mouse", ("wheel_ctrl" if ctrl else "wheel", delta))
                return True
        if msg == WM_XBUTTONDOWN and self.enabled and self.side_enabled:
            which = (int(data.mouseData) >> 16) & 0xFFFF
            if which in (XBUTTON1, XBUTTON2):
                # pure mode: cursor over the text float -> side keys drive the
                # novel only and are swallowed (wheel_capture is set in pure mode)
                over_float = self.wheel_capture and self._over_wheel_rect(x, y)
                if over_float or self.side_global or self._our_active():
                    self.emit("mouse", "next" if which == XBUTTON1 else "prev")
                    return True
            return False
        if msg == WM_MBUTTONDOWN:
            self._mid_down = True
            self._mid_armed = self.enabled and self.middle_menu and self._our_active()
            self._menu_fired = False
            self._mid_moved = 0.0
            self._mid_start = (x, y)
            self._mid_last = (x, y)
            self._press_time = time.time()
            if self._mid_armed:
                self._generation += 1
                timer = threading.Timer(
                    self.long_press_ms / 1000.0, self._long_press, args=(self._generation,)
                )
                timer.daemon = True
                timer.start()
            return False
        if msg == WM_MOUSEMOVE and self._mid_down:
            dx = x - self._mid_last[0]
            dy = y - self._mid_last[1]
            self._mid_last = (x, y)
            total_up = self._mid_start[1] - y
            self._mid_moved += abs(dx) + abs(dy)
            if self._mid_armed and not self._menu_fired:
                if total_up >= self.middle_threshold and abs(x - self._mid_start[0]) < self.middle_threshold:
                    self._menu_fired = True
                    self._mid_armed = False
                    self.emit("mouse", ("middle_menu", x, y))
                    return False
            if not self._menu_fired and (abs(dx) > 1 or abs(dy) > 1):
                self.emit("mouse", ("middle_drag", dx, dy))
            return False
        if msg == WM_MBUTTONUP:
            if self._mid_armed and not self._menu_fired and self._mid_moved < 6:
                held_ms = (time.time() - self._press_time) * 1000
                if held_ms >= self.long_press_ms:
                    self._menu_fired = True
                    self.emit("mouse", ("middle_menu", x, y))
            self._mid_down = False
            self._mid_armed = False
            self._generation += 1
            return False
        return False

    def _over_wheel_rect(self, x, y):
        hwnd = self.wheel_hwnd
        if not hwnd or not user32.IsWindowVisible(hwnd):
            return False
        rect = wintypes.RECT()
        if not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return False
        return rect.left <= x < rect.right and rect.top <= y < rect.bottom

    def _long_press(self, generation):
        if (
            self._mid_down
            and self._mid_armed
            and not self._menu_fired
            and generation == self._generation
            and self._mid_moved < 6
        ):
            self._menu_fired = True
            self.emit("mouse", ("middle_menu", self._mid_last[0], self._mid_last[1]))

    def run(self):
        self._tid = kernel32.GetCurrentThreadId()
        module = kernel32.GetModuleHandleW(None)
        self._hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._proc, module, 0)
        self._ready.set()
        if not self._hook:
            return
        msg = wintypes.MSG()
        while True:
            result = user32.GetMessageW(ctypes.byref(msg), None, 0, 0)
            if result in (0, -1):
                break
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))
        if self._hook:
            user32.UnhookWindowsHookEx(self._hook)
            self._hook = None
