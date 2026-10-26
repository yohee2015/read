import ctypes
import os
import queue
import tkinter as tk
from ctypes import wintypes
from tkinter import filedialog, messagebox

from novel_reader import APP_TITLE, book, themes, tray as tray_commands
from novel_reader.ui.reader import ReaderView
from novel_reader.ui.settings_dialog import SettingsDialog
from novel_reader.ui.toc_panel import TocPanel

user32 = ctypes.windll.user32
user32.GetAncestor.argtypes = [wintypes.HWND, ctypes.c_uint]
user32.GetAncestor.restype = wintypes.HWND
user32.SetForegroundWindow.argtypes = [wintypes.HWND]
user32.SetForegroundWindow.restype = wintypes.BOOL
user32.SetWindowPos.argtypes = [
    wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, wintypes.UINT,
]
user32.SetWindowPos.restype = wintypes.BOOL
GA_ROOT = 2
SWP_NOSIZE = 0x0001
SWP_NOMOVE = 0x0002
SWP_NOZORDER = 0x0004
SWP_NOACTIVATE = 0x0010
HWND_TOPMOST = -1
HWND_NOTOPMOST = -2

JUMP_PLACEHOLDER = "第N章 / 序号 / 关键词"


class MainWindow:
    def __init__(self, root, config):
        self.root = root
        self.cfg = config
        self.q = queue.Queue()
        self.chapters = []
        self.current = 0
        self.book_path = None
        self.pure = False
        self.toc_visible = bool(config.get("window.toc_visible", True))
        self._toc_in_pure = self.toc_visible
        self._saved_geometry = config.get("window.geometry", "980x680+120+80")
        self._note = ""
        self._note_after = None
        self._applied_regex = config.get("chapter_regex", "")
        self.hotkeys = None
        self.mouse = None
        self.tray = None
        self.settings_dialog = None
        self._menu_open = False
        self.colors = themes.derive_colors(config.get("theme.bg"), config.get("theme.fg"))

        root.title(APP_TITLE)
        root.geometry(self._saved_geometry)
        root.minsize(420, 300)
        root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._build_ui()
        self.apply_theme()
        self.apply_window_options()
        self.update_status()
        self.root.bind("<Escape>", lambda e: self.hide_to_tray())
        self.root.bind("<Control-Key-Right>", lambda e: self.nav_chapter(1))
        self.root.bind("<Control-Key-Left>", lambda e: self.nav_chapter(-1))
        self.root.after(15, self._pump)

    def attach(self, hotkeys=None, mouse=None, tray=None):
        self.hotkeys = hotkeys
        self.mouse = mouse
        self.tray = tray

    def _build_ui(self):
        self.toolbar = tk.Frame(self.root, pady=4, padx=6)
        self.toolbar.pack(side="top", fill="x")
        self._buttons = []
        self._entries = []

        def button(label, command, width=None):
            btn = tk.Button(
                self.toolbar, text=label, command=command, bd=0, relief="flat",
                padx=8, pady=2, width=width,
            )
            btn.pack(side="left", padx=2)
            self._buttons.append(btn)
            return btn

        button("打开", self.open_file)
        self.toc_button = button("目录", lambda: self.toggle_toc())
        button("设置", self.open_settings, width=5)

        self.body = tk.Frame(self.root)
        self.body.pack(side="top", fill="both", expand=True)
        self.toc = TocPanel(self.body, self)
        self.jump_entry = self.toc.jump_entry
        self.jump_entry.insert(0, JUMP_PLACEHOLDER)
        self._entries.append(self.jump_entry)
        self.jump_entry.bind("<FocusIn>", self._jump_focus_in)
        self.jump_entry.bind("<FocusOut>", self._jump_focus_out)
        self.jump_entry.bind("<Return>", lambda e: self.do_jump())
        self.reader = ReaderView(self.body, self)

        self.status = tk.Label(self.root, anchor="w", padx=8, pady=3)
        self.status.pack(side="bottom", fill="x")

        if self.toc_visible:
            self.toc.pack(side="left", fill="y")
        self.reader.pack(side="left", fill="both", expand=True)

    def _layout_normal(self):
        self.toolbar.pack(side="top", fill="x")
        if self.toc_visible:
            self.toc.pack(side="left", fill="y")
        self.reader.pack(side="left", fill="both", expand=True)
        self.status.pack(side="bottom", fill="x")

    def _theme_widgets(self):
        yield self.toolbar
        yield self.body
        yield self.status

    def _key_color(self):
        stored = str(self.cfg.get("theme.key_color", "") or "").strip().lower()
        if stored and stored != "#010101":
            return stored
        return themes.key_color_for(self.colors["fg"])

    def apply_theme(self):
        cfg_theme = self.cfg.get("theme", {})
        self.colors = themes.derive_colors(cfg_theme.get("bg"), cfg_theme.get("fg"))
        colors = self.colors
        family = cfg_theme.get("font_family", "微软雅黑")
        size = int(cfg_theme.get("font_size", 15))
        spacing = themes.spacing_pixels(size, float(cfg_theme.get("line_spacing", 1.6)))
        key = self._key_color()
        if self.pure:
            # key may have changed (fg/theme edited while in pure mode) ->
            # re-point transparentcolor or the window renders fully opaque
            self.root.wm_attributes("-transparentcolor", key)
            self.root.after_idle(
                lambda k=key: self.root.wm_attributes("-transparentcolor", k)
            )
        self.root.configure(bg=key if self.pure else colors["bg"])
        frame_bg = key if self.pure else colors["bg"]
        for frame in self._theme_widgets():
            try:
                frame.configure(bg=frame_bg)
            except tk.TclError:
                pass
        for btn in self._buttons:
            btn.configure(
                bg=colors["edge"], fg=colors["fg"],
                activebackground=colors["accent"], activeforeground=colors["bg"],
                font=(family, max(9, size - 2)),
            )
        for entry in self._entries:
            entry.configure(
                bg=colors["edge"], fg=colors["fg"], insertbackground=colors["fg"],
                font=(family, max(9, size - 2)), highlightthickness=0,
            )
        self.status.configure(
            bg=colors["bg"], fg=colors["hint"], font=(family, max(9, size - 3))
        )
        self.toc.apply_style(colors, family, size)
        self.reader.apply_style(colors, family, size, spacing, pure=self.pure, key_color=key)
        alpha = 1.0 if self.pure else float(cfg_theme.get("alpha", 1.0))
        self.root.wm_attributes("-alpha", alpha)

    def apply_window_options(self):
        topmost = bool(self.cfg.get("window.topmost", False))
        self.root.wm_attributes("-topmost", topmost)
        hwnd = user32.GetAncestor(int(self.root.winfo_id()), GA_ROOT)
        if hwnd:
            user32.SetWindowPos(
                hwnd, HWND_TOPMOST if topmost else HWND_NOTOPMOST,
                0, 0, 0, 0, SWP_NOMOVE | SWP_NOSIZE | SWP_NOACTIVATE,
            )

    def apply_settings(self):
        if self.mouse:
            self.mouse.apply_config(self.cfg)
        if self.hotkeys:
            self.hotkeys.set_mapping(dict(self.cfg.get("hotkeys", {})))
        new_regex = self.cfg.get("chapter_regex", "") or ""
        re_split = new_regex != self._applied_regex
        self._applied_regex = new_regex
        self.apply_theme()
        self.apply_window_options()
        self.update_status()
        if re_split and self.book_path:
            self.open_file(self.book_path, restore=True)

    def open_file(self, path=None, restore=True):
        if not path:
            path = filedialog.askopenfilename(
                title="选择小说 txt",
                filetypes=[("文本文件", "*.txt"), ("所有文件", "*.*")],
            )
        if not path:
            return False
        path = os.path.abspath(path)
        try:
            chapters, mode, note = book.load_book(path, self.cfg.get("chapter_regex") or None)
        except OSError as exc:
            messagebox.showerror("打开失败", "无法读取文件：\n%s" % exc, parent=self.root)
            return False
        if not chapters:
            messagebox.showerror("打开失败", "文件没有可显示的内容。", parent=self.root)
            return False
        self.chapters = chapters
        self.book_path = path
        index = 0
        frac = 0.0
        if restore:
            item = (self.cfg.get("reader.progress", {}) or {}).get(path) or {}
            try:
                index = int(item.get("chapter", 0))
                frac = float(item.get("scroll", 0.0))
            except (TypeError, ValueError):
                index, frac = 0, 0.0
        index = max(0, min(index, len(chapters) - 1))
        self.current = index
        self.toc.set_chapters([c.title for c in chapters], index)
        self.reader.show(chapters[index], frac)
        self.toc.highlight(index)
        self.cfg.set("reader.last_book", path)
        self.cfg.save()
        if note:
            self.status_note(note, 6000)
        else:
            self.status_note("已加载 %d 章" % len(chapters), 3000)
        self.update_status()
        return True

    def goto_chapter(self, index):
        if not self.chapters:
            return
        index = max(0, min(int(index), len(self.chapters) - 1))
        self.current = index
        self.reader.show(self.chapters[index], 0.0)
        self.toc.highlight(index)
        if self.book_path:
            self.cfg.remember_progress(self.book_path, index, 0.0)
            self.cfg.save()
        self.update_status()

    def nav_chapter(self, delta):
        if not self.chapters:
            return False
        target = self.current + delta
        if target < 0 or target >= len(self.chapters):
            self.status_note("已经是%s" % ("最后一章" if delta > 0 else "第一章"), 2000)
            return False
        self.goto_chapter(target)
        return True

    def do_jump(self, *args):
        query = self.jump_entry.get()
        if query.strip() == JUMP_PLACEHOLDER:
            return
        index = book.resolve_jump(query, self.chapters, self.current)
        if index is None:
            self.status_note("未找到匹配的章节：%s" % query.strip(), 3000)
            return
        self.goto_chapter(index)
        self.reader.text.focus_set()

    def _jump_focus_in(self, event):
        if self.jump_entry.get() == JUMP_PLACEHOLDER:
            self.jump_entry.delete(0, "end")
            self.jump_entry.configure(fg=self.colors["fg"])

    def _jump_focus_out(self, event):
        if not self.jump_entry.get().strip():
            self.jump_entry.delete(0, "end")
            self.jump_entry.insert(0, JUMP_PLACEHOLDER)
            self.jump_entry.configure(fg=self.colors["hint"])

    def reader_zoom(self, delta):
        current = int(self.cfg.get("theme.font_size", 15))
        size = max(8, min(48, current + delta))
        if size == current:
            return
        self.cfg.set("theme.font_size", size)
        self.cfg.save()
        self.apply_theme()

    def update_status(self):
        parts = []
        if self.chapters:
            name = os.path.splitext(os.path.basename(self.book_path))[0]
            percent = int(round((self.current + 1) * 100 / len(self.chapters)))
            parts.append("《%s》 第 %d/%d 章 · %d%%" % (
                name, self.current + 1, len(self.chapters), percent))
        else:
            parts.append("未打开书籍")
        parts.append("Ctrl+Alt+H 隐藏 · Ctrl+Alt+T 只显文字 · 侧键翻章 · 中键上移菜单 · PgUp/PgDn 翻页")
        text = "  |  ".join(parts)
        if self._note:
            text += "　★ " + self._note
        self.status.configure(text=text)

    def status_note(self, message, ms=4000):
        self._note = message
        if self._note_after:
            self.root.after_cancel(self._note_after)
        self._note_after = self.root.after(ms, self._clear_note)
        self.update_status()

    def _clear_note(self):
        self._note = ""
        self._note_after = None
        self.update_status()

    def toggle_toc(self, value=None):
        if self.pure:
            return
        visible = (not self.toc_visible) if value is None else bool(value)
        if visible == self.toc_visible:
            return
        self.toc_visible = visible
        self.cfg.set("window.toc_visible", visible, save=True)
        if visible:
            self.toc.pack(side="left", fill="y", before=self.reader)
        else:
            self.toc.pack_forget()

    def set_pure(self, on):
        on = bool(on)
        if on == self.pure:
            return
        colors = self.colors
        cfg_theme = self.cfg.get("theme", {})
        key = self._key_color()
        family = cfg_theme.get("font_family", "微软雅黑")
        size = int(cfg_theme.get("font_size", 15))
        spacing = themes.spacing_pixels(size, float(cfg_theme.get("line_spacing", 1.6)))
        if on:
            self._saved_geometry = self.root.geometry()
            self._toc_in_pure = self.toc_visible
            self.toolbar.pack_forget()
            self.status.pack_forget()
            if self.toc_visible:
                self.toc.pack_forget()
            self.root.overrideredirect(True)
            self.root.wm_attributes("-alpha", 1.0)
            self.root.wm_attributes("-transparentcolor", key)
            self.root.configure(bg=key)
            self.reader.set_pure(True)
            self.reader.apply_style(colors, family, size, spacing, pure=True, key_color=key)
            self.root.geometry(self._saved_geometry)
            self.apply_window_options()
            self.root.after_idle(lambda: self.root.wm_attributes("-transparentcolor", key))
            if self.mouse:
                hwnd = user32.GetAncestor(int(self.root.winfo_id()), GA_ROOT)
                self.mouse.wheel_hwnd = int(hwnd or 0)
                self.mouse.wheel_capture = True
        else:
            if self.mouse:
                self.mouse.wheel_capture = False
            self.root.wm_attributes("-alpha", float(cfg_theme.get("alpha", 1.0)))
            self.root.wm_attributes("-transparentcolor", "")
            self.root.overrideredirect(False)
            self.reader.set_pure(False)
            self.reader.apply_style(colors, family, size, spacing, pure=False, key_color=key)
            self.root.configure(bg=colors["bg"])
            self.root.geometry(self._saved_geometry)
            self.apply_window_options()
            self._layout_normal()
        self.pure = on
        self.update_status()

    def toggle_pure(self):
        self.set_pure(not self.pure)

    def hide_to_tray(self, *args):
        self._save_state()
        self.root.withdraw()

    def show_window(self):
        self.root.deiconify()
        self.root.lift()
        self.root.focus_force()
        hwnd = user32.GetAncestor(int(self.root.winfo_id()), GA_ROOT)
        if hwnd:
            user32.SetForegroundWindow(hwnd)

    def toggle_visibility(self):
        if str(self.root.state()) == "withdrawn" or not self.root.winfo_viewable():
            self.show_window()
        else:
            self.hide_to_tray()

    def move_window(self, x, y):
        hwnd = user32.GetAncestor(int(self.root.winfo_id()), GA_ROOT)
        if hwnd:
            user32.SetWindowPos(
                hwnd, None, int(x), int(y), 0, 0,
                SWP_NOSIZE | SWP_NOZORDER | SWP_NOACTIVATE,
            )

    def _post_menu(self, menu, x, y):
        if self._menu_open:
            return
        self._menu_open = True
        try:
            menu.tk_popup(int(x), int(y))
        except tk.TclError:
            pass
        finally:
            try:
                menu.grab_release()
            except tk.TclError:
                pass
            self._menu_open = False

    def _build_theme_menu(self):
        menu = tk.Menu(self.root, tearoff=0, bg=self.colors["edge"], fg=self.colors["fg"],
                       activebackground=self.colors["accent"], activeforeground=self.colors["bg"])
        for key, preset in themes.PRESETS.items():
            menu.add_command(
                label=preset["label"],
                command=lambda k=key: self._use_preset(k),
            )
        menu.add_separator()
        menu.add_command(label="自定义颜色…", command=self.open_settings)
        return menu

    def _theme_menu(self):
        self._post_menu(
            self._build_theme_menu(),
            self.root.winfo_rootx() + 120,
            self.root.winfo_rooty() + 40,
        )

    def _use_preset(self, key):
        preset = themes.PRESETS[key]
        self.cfg.set("theme.preset", key)
        self.cfg.set("theme.bg", preset["bg"])
        self.cfg.set("theme.fg", preset["fg"])
        self.cfg.save()
        self.apply_theme()

    def _build_reader_menu(self):
        colors = self.colors
        family = self.cfg.get("theme.font_family", "微软雅黑")
        size = int(self.cfg.get("theme.font_size", 15))
        menu = tk.Menu(
            self.root, tearoff=0, bg=colors["edge"], fg=colors["fg"],
            activebackground=colors["accent"], activeforeground=colors["bg"],
            font=(family, max(9, size - 2)),
        )
        menu.add_command(label="章节目录" if not self.toc_visible else "隐藏目录",
                         command=lambda: self.toggle_toc())
        menu.add_command(label="跳转到章节…", command=self._focus_jump)
        menu.add_command(label="打开其它 txt…", command=self.open_file)
        menu.add_separator()
        menu.add_command(label="字号 +", command=lambda: self.reader_zoom(1))
        menu.add_command(label="字号 -", command=lambda: self.reader_zoom(-1))
        menu.add_command(label="下一个主题", command=self._next_preset)
        menu.add_command(label="设置…", command=self.open_settings)
        menu.add_separator()
        menu.add_command(label="恢复正常窗口" if self.pure else "只显文字",
                         command=self.toggle_pure)
        topmost = bool(self.cfg.get("window.topmost", False))
        menu.add_command(label="取消窗口置顶" if topmost else "窗口置顶",
                         command=self._toggle_topmost)
        menu.add_command(label="隐藏到托盘", command=self.hide_to_tray)
        menu.add_separator()
        menu.add_command(label="退出", command=self.quit_app)
        return menu

    def popup_reader_menu(self, x, y):
        self._post_menu(self._build_reader_menu(), x, y)

    def _next_preset(self):
        keys = list(themes.PRESETS)
        current = self.cfg.get("theme.preset", "dark")
        index = (keys.index(current) + 1) % len(keys) if current in keys else 0
        self._use_preset(keys[index])

    def _focus_jump(self):
        if self.pure:
            self.set_pure(False)
        if str(self.root.state()) == "withdrawn":
            self.show_window()
        if not self.toc_visible:
            self.toggle_toc(True)
        self.jump_entry.focus_set()
        if self.jump_entry.get() == JUMP_PLACEHOLDER:
            self.jump_entry.select_range(0, "end")

    def open_settings(self, *args):
        if self.settings_dialog is not None and self.settings_dialog.winfo_exists():
            self.settings_dialog.lift()
            self.settings_dialog.focus_set()
            return
        self.settings_dialog = SettingsDialog(self)

    def _on_close(self):
        if bool(self.cfg.get("window.close_to_tray", True)):
            self.hide_to_tray()
            self.status_note("已最小化到托盘，Ctrl+Alt+H 可再次呼出", 4000)
        else:
            self.quit_app()

    def quit_app(self):
        self._save_state()
        for thread in (self.hotkeys, self.mouse, self.tray):
            if thread is not None:
                try:
                    thread.stop()
                except Exception:
                    pass
        self.root.destroy()

    def _save_state(self):
        try:
            state = str(self.root.state())
        except tk.TclError:
            state = "normal"
        if state in ("normal", "iconic", "withdrawn", "zoomed"):
            try:
                geometry = self.root.geometry()
                if geometry:
                    self._saved_geometry = geometry
            except tk.TclError:
                geometry = ""
        self.cfg.set("window.geometry", self._saved_geometry)
        if self.book_path and self.chapters:
            self.cfg.remember_progress(
                self.book_path, self.current, self.reader.frac()
            )
        self.cfg.save()

    def _pump(self):
        while True:
            try:
                kind, payload = self.q.get_nowait()
            except queue.Empty:
                break
            try:
                self._handle_event(kind, payload)
            except Exception as exc:
                try:
                    self.status_note("事件处理出错: %s" % exc, 4000)
                except tk.TclError:
                    pass
        try:
            self.root.after(15, self._pump)
        except tk.TclError:
            pass

    def _handle_event(self, kind, payload):
        if kind == "hotkey":
            action = {
                "hide": self.toggle_visibility,
                "transparent": self.toggle_pure,
                "next": lambda: self.nav_chapter(1),
                "prev": lambda: self.nav_chapter(-1),
            }.get(payload)
            if action:
                action()
        elif kind == "hotkey_error":
            self.status_note(payload, 6000)
        elif kind == "mouse":
            if payload == "next":
                self.nav_chapter(1)
            elif payload == "prev":
                self.nav_chapter(-1)
            elif isinstance(payload, tuple):
                name = payload[0]
                if name == "middle_menu":
                    self.popup_reader_menu(payload[1], payload[2])
                elif name == "middle_drag":
                    self.reader.scroll_drag(payload[2])
                elif name == "wheel":
                    self.reader.scroll_wheel(payload[1])
                elif name == "wheel_ctrl":
                    self.reader_zoom(1 if payload[1] > 0 else -1)
        elif kind == "tray":
            mapping = {
                tray_commands.CMD_RESTORE: self.show_window,
                tray_commands.CMD_TOPMOST: self._toggle_topmost,
                tray_commands.CMD_PREV: lambda: self.nav_chapter(-1),
                tray_commands.CMD_NEXT: lambda: self.nav_chapter(1),
                tray_commands.CMD_TRANSPARENT: self.toggle_pure,
                tray_commands.CMD_SETTINGS: self.open_settings,
                tray_commands.CMD_QUIT: self.quit_app,
            }
            action = mapping.get(int(payload))
            if action:
                action()

    def _toggle_topmost(self):
        value = not bool(self.cfg.get("window.topmost", False))
        self.cfg.set("window.topmost", value, save=True)
        self.apply_window_options()
        self.status_note("窗口置顶已%s" % ("开启" if value else "关闭"), 2000)
