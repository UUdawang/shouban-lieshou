"""盯拍拍卖面板。MVP-0：简单 QTableWidget 展示 active auction_watches。"""
from __future__ import annotations

from typing import Any, Dict, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTableWidget, QTableWidgetItem, QHeaderView
from PySide6.QtGui import QColor, QBrush


HEADERS = [
    "状态", "来源", "剩余", "当前价(日元)", "最高建议(日元)", "出价数", "预估售价(元)", "IP", "打包", "件数", "标题",
]


class AuctionWatchPanel(QTableWidget):
    def __init__(self, parent=None):
        super().__init__(0, len(HEADERS), parent)
        self.setHorizontalHeaderLabels(HEADERS)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableWidget.SelectRows)
        self.setEditTriggers(QTableWidget.NoEditTriggers)
        self.setSortingEnabled(True)
        hdr = self.horizontalHeader()
        widths = [70, 70, 90, 110, 110, 70, 110, 90, 60, 50, 500]
        for i, w in enumerate(widths):
            hdr.resizeSection(i, w)
        hdr.setSectionResizeMode(len(HEADERS) - 1, QHeaderView.Stretch)
        self.verticalHeader().setDefaultSectionSize(24)

    def load_rows(self, rows: List[Dict[str, Any]]):
        self.setRowCount(0)
        for r in rows:
            self.insertRow(0)
            values = self._row_values(r)
            for col_idx, val in enumerate(values):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignCenter if col_idx != len(values) - 1 else Qt.AlignLeft | Qt.AlignVCenter)
                self._colorize(item, col_idx, val, r)
                self.setItem(0, col_idx, item)

    @staticmethod
    def _row_values(r: Dict[str, Any]):
        status_label = {
            "watching": "监控中",
            "over_threshold": "达标",
            "bidded": "已出价",
            "won": "已中标",
            "lost": "未中",
            "canceled": "已结束",
        }.get(r.get("status", "watching"), r.get("status", "watching"))
        end_time = r.get("end_time") or "-"
        remain = AuctionWatchPanel._remain_human(end_time)
        return [
            status_label,
            r.get("source", ""),
            remain,
            f"{r.get('current_jpy', 0):.0f}",
            f"{r.get('max_bid_jpy', 0):.0f}",
            f"{r.get('bid_count', 0)}",
            f"{r.get('estimated_p', 0):.0f}",
            r.get("matched_ip") or ("#" + str(r["ip_id"])) if r.get("ip_id") else "-",
            "是" if r.get("is_lot") else "否",
            f"{r.get('item_count', 1)}",
            r.get("title", ""),
        ]

    @staticmethod
    def _remain_human(end_time_str: str) -> str:
        try:
            import datetime as dt
            end = None
            for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S"):
                try:
                    end = dt.datetime.strptime(end_time_str, fmt)
                    break
                except Exception:
                    pass
            if end is None:
                return "-"
            if end.tzinfo is not None:
                end = end.replace(tzinfo=None)
            delta = end - dt.datetime.now()
            total_sec = int(delta.total_seconds())
            if total_sec <= 0:
                return "已截拍"
            h, rem = divmod(total_sec, 3600)
            m, s = divmod(rem, 60)
            if h > 24:
                return f"{h // 24}天{h % 24}h"
            if h > 0:
                return f"{h}h{m:02d}m"
            return f"{m}m{s:02d}s"
        except Exception:
            return str(end_time_str)[:8]

    @staticmethod
    def _colorize(item: QTableWidgetItem, col_idx: int, _val, row: Dict[str, Any]):
        if col_idx == 0:  # 状态列
            s = row.get("status", "watching")
            if s == "over_threshold":
                item.setForeground(QBrush(QColor("#dc2626")))
                f = item.font()
                f.setBold(True)
                item.setFont(f)
            elif s == "bidded":
                item.setForeground(QBrush(QColor("#ea580c")))
            elif s == "watching":
                item.setForeground(QBrush(QColor("#059669")))
        # 当前价 vs max_bid 提示
        if col_idx == 3:
            cur = row.get("current_jpy", 0)
            mb = row.get("max_bid_jpy") or 0
            if mb and cur >= mb:
                item.setForeground(QBrush(QColor("#dc2626")))
                f = item.font()
                f.setBold(True)
                item.setFont(f)
            elif mb and cur >= mb * 0.9:
                item.setForeground(QBrush(QColor("#ea580c")))
