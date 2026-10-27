# AGENTS.md

Windows-only Tkinter TXT novel reader. Runtime is Python 3.9+ standard library
only; Win32 APIs are called through `ctypes`. No CI, no dependency manifest;
dev-only tools are `flake8` (lint) and PyInstaller (packaging).

## Commands (PowerShell — use `;`, not `&&`)

- Run: `python run.py ["path\to\book.txt"]`
- Unit tests (pure logic, no GUI): `python -m unittest discover -s tests -v`
- One test module: `python -m unittest discover -s tests -p "test_themes.py" -v`
- Lint: `python -m flake8 novel_reader run.py tests --select=F,E9 --max-line-length=120`
- GUI smoke (real window, injects mouse/hotkey input, ~25s, needs interactive desktop):
  `$env:NOVEL_READER_CONFIG="$env:TEMP\novel_reader_smoke.json"; python run.py --smoke "samples/测试小说.txt"`
  Set `NOVEL_READER_SMOKE_OUT` to a file to capture `STEP`/`SMOKE-*` logs.
- Build exe: `.\build.ps1` → `dist\摸鱼阅读.exe` (creates `.venv-build`, installs PyInstaller)

Tests use stdlib `unittest`; there is no pytest config.

## Config

- User config: `%APPDATA%\NovelReader\config.json`; `NOVEL_READER_CONFIG` overrides the path.
  Always set the override for smoke/ad-hoc runs so real user config is not modified.
- Add new defaults to `DEFAULTS` in `novel_reader/config.py`; read/write with dotted
  keys such as `Config.get("theme.fg")` / `Config.set("theme.fg", value)`.

## Architecture

- Entry point: `run.py` → `novel_reader/main.py:main()` → `MainWindow`.
- Hotkey, mouse-hook and tray run on background Win32 threads and only call
  `emit(kind, payload)` into `MainWindow.q`. The Tk thread drains it in
  `MainWindow._pump` every 15 ms. Never touch Tk from those threads — enqueue instead.
- Windows-only imports (`ctypes.windll`) are in `ui/main_window.py`, `hotkeys.py`,
  `mouse_hook.py`, `tray.py`, `smoke.py`; unit tests only cover `book.py` and `themes.py`.
- `ReaderView.text` is `state="disabled"`; switch to `normal` before programmatic edits.
- UI strings are Chinese and source files are UTF-8. Console mojibake in this repo is a
  PowerShell codepage issue, not the file encoding.

## Pure-text mode gotcha

- The `-transparentcolor` key comes from `themes.key_color_for(fg)`, which keeps at least
  `KEY_SAFE_GAP = 24` per RGB channel from the text color. Never key off a color equal or
  near `fg`: that regressed into the whole window appearing as font-colored.
- While pure mode is on, every visible window/frame/Text background must be exactly the
  key. `apply_theme()` must re-point `-transparentcolor` because the key changes with
  theme/font edits; `set_pure(False)` clears it.
- A stored `theme.key_color` is accepted only when `themes.key_gap_ok(fg, key)` passes;
  otherwise fall back to the computed key.
