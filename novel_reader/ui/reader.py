import tkinter as tk
from tkinter import ttk


class ReaderView(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master)
        self.app = app
        self.chapter = None
        self.pure = False
        self._drag_origin = None
        self.text = tk.Text(
            self, wrap="word", relief="flat", bd=0, padx=30, pady=24,
            highlightthickness=0, cursor="xterm", takefocus=True,
            state="disabled", spacing1=0, spacing3=0,
        )
        self.vsb = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=self.vsb.set)
        self.text.grid(row=0, column=0, sticky="nsew")
        self.vsb.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.text.bind("<Button-1>", self._on_press)
        self.text.bind("<B1-Motion>", self._on_drag)
        self.text.bind("<ButtonRelease-1>", self._on_release)
        self.text.bind("<Control-MouseWheel>", self._ctrl_wheel)
        self.text.bind("<MouseWheel>", self._wheel)
        self.text.bind("<Key>", self._on_key)
        self.text.bind("<Next>", self._on_page)
        self.text.bind("<Prior>", self._on_page)

    def apply_style(self, colors, family, size, spacing_px, pure=False, key_color="#010101"):
        bg = key_color if pure else colors["bg"]
        self.configure(bg=bg)
        self.text.configure(
            bg=bg, fg=colors["fg"], insertbackground=colors["fg"],
            selectbackground=colors["accent"], selectforeground=colors["bg"],
            font=(family, size), spacing1=spacing_px, spacing3=spacing_px,
            insertwidth=0,
        )
        self.text.tag_configure(
            "title",
            font=(family, min(48, size + 4), "bold"),
            spacing1=spacing_px * 2,
            spacing3=spacing_px * 2,
            foreground=colors["fg"],
        )

    def set_pure(self, on):
        self.pure = bool(on)
        self.text.configure(cursor="fleur" if self.pure else "xterm")
        if self.pure:
            self.vsb.grid_remove()
        else:
            self.vsb.grid()
            self._drag_origin = None

    def show(self, chapter, frac=0.0):
        self.chapter = chapter
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        body = chapter.body or ""
        first_line = body.split("\n", 1)[0].strip()
        self.text.insert("end", chapter.title + "\n", "title")
        if first_line and first_line.startswith(chapter.title):
            body = body.split("\n", 1)[1] if "\n" in body else ""
        self.text.insert("end", body.lstrip("\n"))
        self.text.configure(state="disabled")
        self.text.mark_set("insert", "1.0")
        if frac:
            self.text.update_idletasks()
        self.moveto(frac)

    def frac(self):
        try:
            return float(self.text.yview()[0])
        except tk.TclError:
            return 0.0

    def moveto(self, frac):
        try:
            self.text.yview_moveto(max(0.0, min(1.0, float(frac))))
        except tk.TclError:
            pass

    def scroll_drag(self, dy):
        try:
            first, last = self.text.yview()
        except tk.TclError:
            return
        if last - first >= 0.999:
            return
        height = self.text.winfo_height()
        if height <= 1:
            return
        total = height / (last - first)
        self.moveto(first - dy / total)

    def at_top(self):
        return self.text.yview()[0] <= 0.0005

    def at_bottom(self):
        return self.text.yview()[1] >= 0.9995

    def scroll_page(self, direction):
        self.text.yview_scroll(direction, "pages")

    def scroll_wheel(self, delta):
        if not delta:
            return
        lines = int(round(delta / 40.0)) or (1 if delta > 0 else -1)
        self.text.yview_scroll(-lines, "units")

    def _wheel(self, event):
        if event.state & 0x4:
            return None
        self.scroll_wheel(event.delta or 0)
        return "break"

    def _on_press(self, event):
        self.text.focus_set()
        if self.pure:
            self._drag_origin = (
                event.x_root, event.y_root, self.text.winfo_rootx(), self.text.winfo_rooty()
            )
            return "break"
        return None

    def _on_drag(self, event):
        if not (self.pure and self._drag_origin):
            return None
        start_x, start_y, win_x, win_y = self._drag_origin
        dx = event.x_root - start_x
        dy = event.y_root - start_y
        if abs(dx) + abs(dy) > 3:
            self.app.move_window(win_x + dx, win_y + dy)
        return "break"

    def _on_release(self, event):
        self._drag_origin = None
        return None

    def _ctrl_wheel(self, event):
        self.app.reader_zoom(1 if (event.delta or 1) > 0 else -1)
        return "break"

    def _on_key(self, event):
        if event.keysym == "Escape":
            self.app.hide_to_tray()
            return "break"
        if event.state & 0x4:
            key = event.keysym.lower()
            if key == "right":
                self.app.nav_chapter(1)
                return "break"
            if key == "left":
                self.app.nav_chapter(-1)
                return "break"
            if key in ("plus", "minus", "equal", "equal_sign", "kp_add", "kp_subtract"):
                self.app.reader_zoom(1 if key != "minus" and key != "kp_subtract" else -1)
                return "break"
            if key in ("c", "a"):
                return None
        return "break"

    def _on_page(self, event):
        direction = 1 if event.keysym == "Next" else -1
        if direction > 0 and self.at_bottom():
            self.app.nav_chapter(1)
            return "break"
        if direction < 0 and self.at_top():
            self.app.nav_chapter(-1)
            return "break"
        self.scroll_page(direction)
        return "break"
