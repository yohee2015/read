# 摸鱼阅读（Novel Reader）

Windows 10 下的本地 TXT 小说阅读器，为上班摸鱼场景设计：
轻量（纯标准库 + Tkinter）、可一键隐藏到托盘、可整窗只显示文字（背景全透明）。

## 功能

- 导入本地 TXT（自动识别 UTF-8 / GB18030 / UTF-16 等编码），按章节自动分割
- 章节目录点击跳转，支持输入 `第12章` / `12` / 章节关键词跳转
- 自定义背景色 / 文字颜色，内置素白、暗夜、护眼、羊皮纸 4 套主题
- 字号、行距、字体可调（Ctrl+滚轮、中键菜单、设置对话框）；顶部工具栏仅「打开 / 目录 / 设置」3 个按钮
- 窗口可自由拉伸，几何位置自动记忆
- **全透明只显文字模式**：背景完全穿透，只剩文字浮在桌面/其它软件上，仍可点击、滚轮翻页
  （文字始终 100% 不透明、清晰；键色与文字色保持至少 24 级安全间隔，
  避免整窗背景被色键误判为字体色，抗锯齿边缘只会带极浅的键色过渡；
  与之配套的「窗口不透明度」滑条只调节正常窗口整体，含文字）
- 只显文字模式下：光标在文字浮层范围内**滚轮翻页并挡住下层应用**（Ctrl+滚轮缩放字号），范围外滚轮照常作用于后面的窗口；
  中键菜单/托盘菜单均可开关**窗口置顶**（默认开启，浮层可压在其它窗口之上）
- 鼠标快捷键（低级鼠标钩子）：
  - 鼠标侧键：后退 = 下一章，前进 = 上一章（默认仅本窗口激活时生效，可在设置中改为全局；
    只显文字模式下光标在文字浮层范围内也仅翻小说，不触发下层应用的前进/后退）
  - 中键按住向上拖动 / 长按：弹出目录·跳转·主题·设置菜单
  - 中键按住向下/横向拖动：拖拽滚动页面
  - 滚轮：正常翻页滚动
- 全局快捷键（默认 `Ctrl+Alt+H` 隐藏/显示，`Ctrl+Alt+T` 只显文字，`Ctrl+Alt+N/P` 下/上一章，均可改）
- 系统托盘：左键恢复窗口，右键菜单（显示/置顶/上下章/只显文字/设置/退出）
- 默认不在任务栏和 Alt+Tab 中显示，只在右下角托盘保留图标（可在设置中关闭）；
  左键托盘图标或 `Ctrl+Alt+H` 呼出窗口
- 关闭按钮默认最小化到托盘；每本书的阅读进度自动记忆

## 快速开始

```powershell
# 直接运行（需要 Python 3.9+，Windows）
python run.py

# 打开指定书籍
python run.py "D:\book\我的小说.txt"
```

## 打包成单文件 exe

```powershell
.\build.ps1
# 产物: dist\摸鱼阅读.exe
```

## 配置文件

位于 `%APPDATA%\NovelReader\config.json`（主题色、字号、快捷键、窗口几何、每本书进度、章节自定义正则）。
删除该文件即可恢复默认。环境变量 `NOVEL_READER_CONFIG` 可指定其它路径（用于测试）。

## 章节识别

内置规则匹配行首的 `第X章/第X回/第X节/卷/序章/楔子/引子/尾声/终章/番外/Chapter N` 等
（X 支持阿拉伯数字与中文数字，标题行不超过 60 字且不以句号类标点结尾）。
识别不到时按字数自动分节；也可在「设置 → 章节分割」里填写自定义正则（对每行匹配，如 `^第\d+章`）。

## 开发与测试

```powershell
# 单元测试（章节分割 / 编码识别 / 跳转解析）
python -m unittest discover -s tests -v

# 冒烟测试：自动开窗、加载样例、切换纯透明、注入鼠标侧键/中键拖动、注入热键消息等
$env:NOVEL_READER_CONFIG = "$env:TEMP\novel_reader_smoke.json"
python run.py --smoke "samples/测试小说.txt"

# 代码检查
python -m flake8 novel_reader run.py tests --select=F,E9 --max-line-length=120
```

## 目录结构

```
novel_reader/
  book.py            TXT 解码与章节分割
  config.py          配置读写（%APPDATA%\NovelReader\config.json）
  themes.py          主题预设与配色推导
  hotkeys.py         RegisterHotKey 全局快捷键（后台消息线程）
  mouse_hook.py      WH_MOUSE_LL 低级鼠标钩子
  tray.py            Shell_NotifyIcon 托盘 + 原生右键菜单
  smoke.py           --smoke 自动化冒烟（鼠标/热键事件注入）
  main.py            入口装配
  ui/
    main_window.py   主窗口、事件泵、纯透明模式
    reader.py        Text 阅读区（滚动/翻章/字号）
    toc_panel.py     章节目录
    settings_dialog.py 设置对话框
tools/gen_icon.py    生成 assets/icon.ico
tests/               单元测试与样例
run.py               启动脚本
build.ps1            PyInstaller 打包脚本
```

## 说明

- 侧键默认仅在阅读器处于前台时生效，避免抢走浏览器的前进/后退；可在设置里开启全局。
- 「只显文字」模式下窗口无边框，按住文字拖动可移动窗口，`Ctrl+Alt+T` 或菜单可恢复。
- 本工具仅供个人本地阅读使用，请勿用于传播未经授权的内容。
