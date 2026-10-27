import copy
import re
import tkinter as tk
from tkinter import colorchooser, messagebox, ttk

from novel_reader import hotkeys as hotkey_utils
from novel_reader.config import DEFAULTS
from novel_reader import themes

MODIFIER_KEYSYMS = {
    "control_l", "control_r", "shift_l", "shift_r", "alt_l", "alt_r",
    "super_l", "super_r", "meta_l", "meta_r", "win_l", "win_r",
    "caps_lock", "num_lock", "scroll_lock", "print",
}
KEY_ALIASES = {
    "return": "enter", "prior": "pageup", "next": "pagedown",
    "escape": "esc", "iso_left_tab": "tab",
}
HOTKEY_FIELDS = (
    ("hide", "隐藏/显示窗口"),
    ("transparent", "只显文字模式"),
    ("next", "下一章"),
    ("prev", "上一章"),
)


def build_combo(event):
    state = event.state
    mods = []
    if state & 0x0001:
        mods.append("shift")
    if state & 0x0004:
        mods.append("ctrl")
    if state & (0x0008 | 0x20000):
        mods.append("alt")
    if state & (0x0040 | 0x80000):
        mods.append("win")
    key = event.keysym.lower()
    if key in MODIFIER_KEYSYMS:
        return None
    key = KEY_ALIASES.get(key, key)
    if len(key) == 1:
        pass
    elif re.fullmatch(r"f\d{1,2}", key):
        pass
    elif key in (
        "enter", "esc", "space", "tab", "backspace", "delete", "insert",
        "home", "end", "left", "right", "up", "down", "pageup", "pagedown",
        "pause", "printscreen",
    ):
        pass
    else:
        return None
    if not mods:
        return None
    return "+".join(mods + [key])


class SettingsDialog(tk.Toplevel):
    def __init__(self, app):
        super().__init__(app.root)
        self.app = app
        self.title("设置 - 摸鱼阅读")
        self.resizable(False, False)
        self.transient(app.root)
        self.configure(bg=app.colors["bg"])
        self._recording = None
        self._build_vars()
        self._build_ui()
        self.grab_set()
        self.bind("<Escape>", lambda e: self.destroy())

    def _build_vars(self):
        theme = self.app.cfg.get("theme", {})
        hotkeys = self.app.cfg.get("hotkeys", {})
        mouse = self.app.cfg.get("mouse", {})
        window = self.app.cfg.get("window", {})
        self.v_bg = tk.StringVar(value=theme.get("bg", "#1e1e1e"))
        self.v_fg = tk.StringVar(value=theme.get("fg", "#d4d4d4"))
        self.v_family = tk.StringVar(value=theme.get("font_family", "宋体"))
        self.v_size = tk.IntVar(value=int(theme.get("font_size", 13)))
        self.v_spacing = tk.DoubleVar(value=float(theme.get("line_spacing", 1.0)))
        self.v_alpha = tk.DoubleVar(value=float(theme.get("alpha", 1.0)))
        self.v_topmost = tk.BooleanVar(value=bool(window.get("topmost", False)))
        self.v_close_tray = tk.BooleanVar(value=bool(window.get("close_to_tray", True)))
        self.v_hide_taskbar = tk.BooleanVar(value=bool(window.get("hide_taskbar", True)))
        self.v_mouse_on = tk.BooleanVar(value=bool(mouse.get("enabled", True)))
        self.v_side = tk.BooleanVar(value=bool(mouse.get("side_buttons", True)))
        self.v_side_global = tk.BooleanVar(value=bool(mouse.get("side_global", False)))
        self.v_middle_menu = tk.BooleanVar(value=bool(mouse.get("middle_menu", True)))
        self.v_regex = tk.StringVar(value=self.app.cfg.get("chapter_regex", ""))
        self.v_hotkeys = {
            name: tk.StringVar(value=hotkeys.get(name, "")) for name, _ in HOTKEY_FIELDS
        }

    def _frame(self, parent, text):
        frame = tk.LabelFrame(parent, text=text, bd=1, relief="groove",
                              bg=self.app.colors["bg"], fg=self.app.colors["fg"],
                              padx=10, pady=8)
        frame.pack(fill="x", padx=10, pady=(8, 0))
        return frame

    def _build_ui(self):
        colors = self.app.colors
        theme_frame = self._frame(self, "主题与字体")
        presets = tk.Frame(theme_frame, bg=colors["bg"])
        presets.pack(fill="x")
        for key, preset in themes.PRESETS.items():
            tk.Button(
                presets, text=preset["label"], width=8,
                command=lambda k=key: self._use_preset(k),
            ).pack(side="left", padx=(0, 6))
        row1 = tk.Frame(theme_frame, bg=colors["bg"])
        row1.pack(fill="x", pady=(8, 0))
        tk.Button(row1, text="背景色", width=8, command=self._pick_bg).pack(side="left")
        self.bg_sample = tk.Label(row1, textvariable=self.v_bg, width=10, bg=self.v_bg.get(),
                                  fg=self.v_fg.get())
        self.bg_sample.pack(side="left", padx=6)
        tk.Button(row1, text="文字颜色", width=8, command=self._pick_fg).pack(side="left", padx=(10, 0))
        self.fg_sample = tk.Label(row1, textvariable=self.v_fg, width=10, bg=self.v_fg.get(),
                                  fg=self.v_bg.get())
        self.fg_sample.pack(side="left", padx=6)
        row2 = tk.Frame(theme_frame, bg=colors["bg"])
        row2.pack(fill="x", pady=(8, 0))
        tk.Label(row2, text="字体", bg=colors["bg"], fg=colors["fg"]).pack(side="left")
        families = ["微软雅黑", "宋体", "楷体", "黑体", "仿宋", "等线", "Arial", "Times New Roman", "Consolas"]
        family_entry = ttk.Combobox(row2, textvariable=self.v_family, values=families, width=10)
        family_entry.pack(side="left", padx=6)
        tk.Label(row2, text="字号", bg=colors["bg"], fg=colors["fg"]).pack(side="left", padx=(10, 0))
        tk.Spinbox(row2, from_=8, to=48, textvariable=self.v_size, width=5).pack(side="left", padx=4)
        tk.Label(row2, text="行距", bg=colors["bg"], fg=colors["fg"]).pack(side="left", padx=(10, 0))
        tk.Scale(row2, from_=1.0, to=3.0, resolution=0.1, orient="horizontal",
                 variable=self.v_spacing, length=140, bg=colors["bg"], fg=colors["fg"],
                 highlightthickness=0, bd=0).pack(side="left", padx=4)

        window_frame = self._frame(self, "窗口")
        row3 = tk.Frame(window_frame, bg=colors["bg"])
        row3.pack(fill="x")
        tk.Scale(row3, from_=0.3, to=1.0, resolution=0.05, orient="horizontal",
                 variable=self.v_alpha, length=200, label="窗口不透明度(整体,含文字)",
                 bg=colors["bg"], fg=colors["fg"], highlightthickness=0, bd=0).pack(side="left")
        tk.Label(window_frame,
                 text="「只显文字」模式始终背景全透明、文字100%清晰，不受此滑条影响",
                 bg=colors["bg"], fg=colors["hint"], anchor="w").pack(fill="x", pady=(2, 0))
        row4 = tk.Frame(window_frame, bg=colors["bg"])
        row4.pack(fill="x", pady=(4, 0))
        tk.Checkbutton(row4, text="窗口置顶", variable=self.v_topmost,
                       bg=colors["bg"], fg=colors["fg"], activebackground=colors["bg"],
                       activeforeground=colors["fg"], selectcolor=colors["edge"],
                       highlightthickness=0).pack(side="left")
        tk.Checkbutton(row4, text="关闭按钮最小化到托盘", variable=self.v_close_tray,
                       bg=colors["bg"], fg=colors["fg"], activebackground=colors["bg"],
                       activeforeground=colors["fg"], selectcolor=colors["edge"],
                       highlightthickness=0).pack(side="left", padx=(16, 0))
        tk.Checkbutton(window_frame, text="不在任务栏显示（仅托盘图标，Alt+Tab 也不显示）",
                       variable=self.v_hide_taskbar, anchor="w",
                       bg=colors["bg"], fg=colors["fg"], activebackground=colors["bg"],
                       activeforeground=colors["fg"], selectcolor=colors["edge"],
                       highlightthickness=0).pack(fill="x", pady=(4, 0))

        mouse_frame = self._frame(self, "鼠标快捷键")
        row5 = tk.Frame(mouse_frame, bg=colors["bg"])
        row5.pack(fill="x")
        checks = (
            (self.v_mouse_on, "启用鼠标快捷键"),
            (self.v_side, "侧键翻章(后退=下一章/前进=上一章)"),
            (self.v_side_global, "侧键全局生效(不影响其它程序请关闭)"),
            (self.v_middle_menu, "中键上移/长按弹出菜单"),
        )
        for i, (var, label) in enumerate(checks):
            tk.Checkbutton(row5, text=label, variable=var, anchor="w",
                           bg=colors["bg"], fg=colors["fg"], activebackground=colors["bg"],
                           activeforeground=colors["fg"], selectcolor=colors["edge"],
                           highlightthickness=0).grid(row=i, column=0, sticky="w")

        hotkey_frame = self._frame(self, "全局快捷键")
        self._record_entries = {}
        for i, (name, label) in enumerate(HOTKEY_FIELDS):
            row = tk.Frame(hotkey_frame, bg=colors["bg"])
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label, width=16, anchor="w",
                     bg=colors["bg"], fg=colors["fg"]).pack(side="left")
            entry = tk.Entry(row, textvariable=self.v_hotkeys[name], width=18,
                             bg=colors["edge"], fg=colors["fg"], insertbackground=colors["fg"],
                             highlightthickness=0, relief="flat")
            entry.pack(side="left", padx=6)
            button = tk.Button(row, text="录制", width=6,
                               command=lambda n=name: self._start_record(n))
            button.pack(side="left")
            self._record_entries[name] = (entry, button)
        tk.Label(hotkey_frame, text="点「录制」后直接按下组合键（需含 Ctrl/Alt/Shift/Win），或手动输入",
                 bg=colors["bg"], fg=colors["hint"], anchor="w").pack(fill="x", pady=(6, 0))

        regex_frame = self._frame(self, "章节分割")
        row6 = tk.Frame(regex_frame, bg=colors["bg"])
        row6.pack(fill="x")
        tk.Label(row6, text="自定义正则", bg=colors["bg"], fg=colors["fg"]).pack(side="left")
        tk.Entry(row6, textvariable=self.v_regex, width=46, bg=colors["edge"],
                 fg=colors["fg"], insertbackground=colors["fg"], highlightthickness=0,
                 relief="flat").pack(side="left", padx=6)
        tk.Label(regex_frame, text="留空使用内置规则（第X章/第X回/序章/Chapter N 等）；正则对每行匹配，如 ^第\\d+章",
                 bg=colors["bg"], fg=colors["hint"], anchor="w").pack(fill="x", pady=(4, 0))

        actions = tk.Frame(self, bg=colors["bg"])
        actions.pack(fill="x", padx=10, pady=12)
        tk.Button(actions, text="应用", width=8, command=self._apply).pack(side="left")
        tk.Button(actions, text="确定", width=8, command=lambda: (self._apply(), self.destroy())
                  ).pack(side="left", padx=6)
        tk.Button(actions, text="取消", width=8, command=self.destroy).pack(side="left", padx=6)
        tk.Button(actions, text="恢复默认", width=10, command=self._reset_defaults).pack(side="right")

    def _refresh_samples(self, *args):
        try:
            self.bg_sample.configure(bg=self.v_bg.get(), fg=self.v_fg.get())
            self.fg_sample.configure(bg=self.v_fg.get(), fg=self.v_bg.get())
        except tk.TclError:
            pass

    def _use_preset(self, key):
        preset = themes.PRESETS[key]
        self.v_bg.set(preset["bg"])
        self.v_fg.set(preset["fg"])
        self._refresh_samples()

    def _pick_bg(self):
        color = colorchooser.askcolor(color=self.v_bg.get(), title="选择背景色", parent=self)
        if color and color[1]:
            self.v_bg.set(color[1])
            self._refresh_samples()

    def _pick_fg(self):
        color = colorchooser.askcolor(color=self.v_fg.get(), title="选择文字颜色", parent=self)
        if color and color[1]:
            self.v_fg.set(color[1])
            self._refresh_samples()

    def _start_record(self, name):
        if self._recording:
            self._stop_record()
        entry, button = self._record_entries[name]
        self._recording = (name, entry, button)
        button.configure(text="按下...")
        entry.delete(0, "end")
        entry.insert(0, "请按下组合键")
        entry.focus_set()
        entry.bind("<KeyPress>", self._on_record_key, add="+")

    def _stop_record(self):
        if not self._recording:
            return
        _, entry, button = self._recording
        try:
            entry.unbind("<KeyPress>")
        except tk.TclError:
            pass
        button.configure(text="录制")
        self._recording = None

    def _on_record_key(self, event):
        name, entry, _ = self._recording
        combo = build_combo(event)
        if combo:
            try:
                hotkey_utils.parse_combo(combo)
            except ValueError as exc:
                entry.delete(0, "end")
                entry.insert(0, str(exc))
                return "break"
            entry.delete(0, "end")
            entry.insert(0, combo)
            self.v_hotkeys[name].set(combo)
            self._stop_record()
        return "break"

    def _reset_defaults(self):
        defaults = copy.deepcopy(DEFAULTS)
        theme = defaults["theme"]
        self.v_bg.set(theme["bg"])
        self.v_fg.set(theme["fg"])
        self.v_family.set(theme["font_family"])
        self.v_size.set(theme["font_size"])
        self.v_spacing.set(theme["line_spacing"])
        self.v_alpha.set(theme["alpha"])
        self.v_topmost.set(defaults["window"]["topmost"])
        self.v_close_tray.set(defaults["window"]["close_to_tray"])
        self.v_hide_taskbar.set(defaults["window"]["hide_taskbar"])
        self.v_mouse_on.set(defaults["mouse"]["enabled"])
        self.v_side.set(defaults["mouse"]["side_buttons"])
        self.v_side_global.set(defaults["mouse"]["side_global"])
        self.v_middle_menu.set(defaults["mouse"]["middle_menu"])
        self.v_regex.set("")
        for name, _ in HOTKEY_FIELDS:
            self.v_hotkeys[name].set(defaults["hotkeys"][name])
        self._refresh_samples()

    def _apply(self):
        regex = self.v_regex.get().strip()
        if regex:
            try:
                re.compile(regex)
            except re.error as exc:
                messagebox.showerror("正则无效", "章节正则无法编译：\n%s" % exc, parent=self)
                return False
        cfg = self.app.cfg
        cfg.set("theme.bg", self.v_bg.get())
        cfg.set("theme.fg", self.v_fg.get())
        cfg.set("theme.font_family", self.v_family.get())
        cfg.set("theme.font_size", int(self.v_size.get()))
        cfg.set("theme.line_spacing", float(self.v_spacing.get()))
        cfg.set("theme.alpha", float(self.v_alpha.get()))
        cfg.set("window.topmost", bool(self.v_topmost.get()))
        cfg.set("window.close_to_tray", bool(self.v_close_tray.get()))
        cfg.set("window.hide_taskbar", bool(self.v_hide_taskbar.get()))
        cfg.set("mouse.enabled", bool(self.v_mouse_on.get()))
        cfg.set("mouse.side_buttons", bool(self.v_side.get()))
        cfg.set("mouse.side_global", bool(self.v_side_global.get()))
        cfg.set("mouse.middle_menu", bool(self.v_middle_menu.get()))
        cfg.set("chapter_regex", regex)
        for name, _ in HOTKEY_FIELDS:
            value = self.v_hotkeys[name].get().strip()
            if value:
                try:
                    hotkey_utils.parse_combo(value)
                except ValueError as exc:
                    messagebox.showerror("快捷键无效", "%s\n%s" % (name, exc), parent=self)
                    return False
            cfg.set("hotkeys.%s" % name, value)
        cfg.save()
        self.app.apply_settings()
        return True
