import os
import sys
import tkinter as tk

from novel_reader import APP_TITLE, __version__
from novel_reader.config import Config
from novel_reader.hotkeys import HotkeyThread
from novel_reader.mouse_hook import MouseHook
from novel_reader.tray import TrayIcon
from novel_reader.ui.main_window import MainWindow


def resource_path(relative):
    base = getattr(sys, "_MEIPASS", os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    return os.path.join(base, relative)


def build_parser(argv):
    smoke = "--smoke" in argv
    args = [a for a in argv if not a.startswith("--")]
    return smoke, (args[0] if args else None)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    smoke, initial_file = build_parser(argv)

    config = Config()
    root = tk.Tk()
    root.title(APP_TITLE)
    window = MainWindow(root, config)

    hotkeys = HotkeyThread(lambda kind, payload: window.q.put((kind, payload)))
    hotkeys.set_mapping(dict(config.get("hotkeys", {})))
    mouse = MouseHook(lambda kind, payload: window.q.put((kind, payload)))
    mouse.apply_config(config)
    icon = resource_path(os.path.join("assets", "icon.ico"))
    tray = TrayIcon(icon, "%s v%s" % (APP_TITLE, __version__),
                    lambda kind, payload: window.q.put((kind, payload)))
    window.attach(hotkeys=hotkeys, mouse=mouse, tray=tray)

    hotkeys.start()
    mouse.start()
    tray.start()
    hotkeys.wait_ready()
    mouse.wait_ready()
    tray.wait_ready()

    start_file = initial_file or config.get("reader.last_book")
    if start_file and os.path.exists(start_file):
        window.open_file(start_file, restore=True)
    else:
        window.status_note("点击「打开」选择本地 txt 开始阅读", 8000)

    if smoke:
        from novel_reader.smoke import SmokeRunner
        SmokeRunner(root, window, hotkeys, mouse, tray).start()

    print("MAINLOOP", flush=True)
    try:
        root.mainloop()
    finally:
        for thread in (hotkeys, mouse, tray):
            try:
                thread.stop()
            except Exception:
                pass
        for thread in (hotkeys, mouse, tray):
            thread.join(2)
    return 0


if __name__ == "__main__":
    sys.exit(main())
