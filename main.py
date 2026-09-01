"""手办套利监控 MVP-0 主入口。
运行：python main.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# 保证以项目根目录为基准import，无论从哪里启动
BASE_DIR = Path(__file__).resolve().parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


def bootstrap():
    """初始化 DB + 种子数据。返回 True 表示一切OK。"""
    from src.models import init_database
    init_database()
    from seed_data import seed_if_empty
    n = seed_if_empty()
    if n > 0:
        print(f"[init] 首次启动，已导入 {n} 个初始 IP + 对应角色。")
    return True


def main():
    bootstrap()
    # 导入放 bootstrap 之后，保证 DB tables 存在后再让 UI 层import
    from PySide6.QtWidgets import QApplication, QSystemTrayIcon
    from PySide6.QtGui import QIcon
    from src.ui import MainWindow
    from config import ensure_dirs

    ensure_dirs()

    app = QApplication(sys.argv)
    app.setApplicationName("手办套利监控 MVP-0")

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("[warn] 系统托盘不可用，桌面通知功能会退化为仅日志显示。")

    win = MainWindow()
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
