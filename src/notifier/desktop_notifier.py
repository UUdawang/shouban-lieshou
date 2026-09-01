"""多渠道推送模块。MVP-0 先实现桌面通知，微信/邮件接口预留。"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, List, Optional


@dataclass
class PushMessage:
    title: str
    body: str
    level: str = "info"  # info / warn / danger
    payload: Optional[dict] = None  # 展示用的结构化数据


class DesktopNotifier:
    """桌面推送。MVP-0：优先用 PySide6 QSystemTrayIcon.showMessage；
    没装 Qt 时回退到终端打印，保证脚本模式也能跑。"""

    def __init__(self):
        self._tray = None  # UI 启动后会注入 QSystemTrayIcon
        self._fallback_callbacks: List[Callable[[PushMessage], None]] = []

    def bind_tray(self, tray_icon) -> None:
        """UI 层创建完系统托盘图标后注入。"""
        self._tray = tray_icon

    def add_fallback(self, cb: Callable[[PushMessage], None]) -> None:
        """非Qt环境下的回调（如 UI 中的日志窗口追加、终端打印）。"""
        self._fallback_callbacks.append(cb)

    def push(self, msg: PushMessage) -> None:
        # 图标: Qt 枚举 0=NoIcon 1=Information 2=Warning 3=Critical
        icon_map = {"info": 1, "warn": 2, "danger": 3}
        icon = icon_map.get(msg.level, 1)
        if self._tray is not None:
            try:
                # 消息最多显示 15 秒，多数平台仍会自己限制长度
                self._tray.showMessage(msg.title, msg.body, icon, 15000)
            except Exception:
                pass
        for cb in self._fallback_callbacks:
            try:
                cb(msg)
            except Exception:
                pass

    def info(self, title: str, body: str, **kwargs):
        self.push(PushMessage(title, body, "info", kwargs.get("payload")))

    def warn(self, title: str, body: str, **kwargs):
        self.push(PushMessage(title, body, "warn", kwargs.get("payload")))

    def danger(self, title: str, body: str, **kwargs):
        self.push(PushMessage(title, body, "danger", kwargs.get("payload")))


# ========== 其他渠道（MVP-0 仅占位，后续补实现） ==========
class WeChatNotifier:
    def push(self, msg: PushMessage) -> None:
        # TODO: 接企业微信机器人或 Server 酱
        pass


class EmailNotifier:
    def push(self, msg: PushMessage) -> None:
        # TODO: 接 SMTP
        pass


# ========== 对外单例 ==========
notifier = DesktopNotifier()
wechat_notifier = WeChatNotifier()
email_notifier = EmailNotifier()


def push_all(msg: PushMessage, channels=("desktop", "wechat", "email")) -> None:
    if "desktop" in channels:
        notifier.push(msg)
    if "wechat" in channels:
        wechat_notifier.push(msg)
    if "email" in channels:
        email_notifier.push(msg)
