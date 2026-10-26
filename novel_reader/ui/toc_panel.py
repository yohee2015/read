import tkinter as tk
from tkinter import ttk


class TocPanel(tk.Frame):
    def __init__(self, master, app):
        super().__init__(master, width=210)
        self.app = app
        self.pack_propagate(False)
        header = tk.Frame(self)
        header.pack(fill="x", padx=6, pady=(6, 2))
        self.title_label = tk.Label(header, text="目录", anchor="w")
        self.title_label.pack(side="left", fill="x", expand=True)
        self.close_btn = tk.Button(header, text="×", width=2, bd=0, relief="flat",
                                   command=lambda: app.toggle_toc(False))
        self.close_btn.pack(side="right")
        self.jump_entry = tk.Entry(self, relief="flat", bd=0, highlightthickness=0)
        self.jump_entry.pack(fill="x", padx=6, pady=(0, 4))
        body = tk.Frame(self)
        body.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.listbox = tk.Listbox(body, activestyle="none", exportselection=False,
                                  relief="flat", bd=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(body, orient="vertical", command=self.listbox.yview)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        self.listbox.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        self.listbox.bind("<<ListboxSelect>>", self._on_select)
        self.listbox.bind("<Double-Button-1>", self._on_select)

    def apply_style(self, colors, family, size):
        style = {
            "bg": colors["bg"], "fg": colors["fg"],
            "selectbackground": colors["accent"], "selectforeground": colors["bg"],
            "highlightthickness": 0, "font": (family, max(9, size - 1)),
        }
        self.configure(bg=colors["bg"], highlightthickness=0)
        self.title_label.configure(bg=colors["bg"], fg=colors["accent"],
                                   font=(family, size, "bold"))
        self.close_btn.configure(bg=colors["bg"], fg=colors["hint"],
                                 activebackground=colors["bg"], activeforeground=colors["fg"])
        self.listbox.configure(**style)

    def set_chapters(self, titles, current=0):
        self.listbox.delete(0, "end")
        for i, title in enumerate(titles):
            self.listbox.insert("end", " %s" % title)
        self.highlight(current)

    def highlight(self, index):
        if self.listbox.size() <= 0:
            return
        index = max(0, min(index, self.listbox.size() - 1))
        self.listbox.selection_clear(0, "end")
        self.listbox.selection_set(index)
        self.listbox.activate(index)
        self.listbox.see(index)

    def _on_select(self, event):
        selection = self.listbox.curselection()
        if selection:
            self.app.goto_chapter(selection[0])
