"""候选商品列表表格。QTableView + QStandardItemModel 展示 candidate_items。"""
from __future__ import annotations

from typing import Any, Dict, List

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QBrush
from PySide6.QtWidgets import QTableView, QHeaderView
from PySide6.QtGui import QStandardItemModel, QStandardItem


COLUMNS = [
    ("时间", "snapshot_at", 140),
    ("IP", "matched_ip", 100),
    ("类型", "is_lot", 60),
    ("件数", "item_count", 50),
    ("商品价(日元)", "price_jpy", 90),
    ("到手价(元)", "total_cost", 90),
    ("闲鱼估价(元)", "estimated_p", 100),
    ("毛利(元)", "net_profit", 80),
    ("利润率", "profit_rate", 80),
    ("来源", "source", 70),
    ("标题", "title", 420),
]


class CandidateTable(QTableView):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = QStandardItemModel(0, len(COLUMNS), self)
        self._model.setHorizontalHeaderLabels([c[0] for c in COLUMNS])
        self.setModel(self._model)
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableView.SelectRows)
        self.setEditTriggers(QTableView.NoEditTriggers)
        self.setSortingEnabled(True)
        header = self.horizontalHeader()
        for i, (_, _, w) in enumerate(COLUMNS):
            header.resizeSection(i, w)
        header.setSectionResizeMode(len(COLUMNS) - 1, QHeaderView.Stretch)
        self.verticalHeader().setDefaultSectionSize(24)

    def load_rows(self, rows: List[Dict[str, Any]]):
        self._model.setRowCount(0)
        for r in rows:
            items = []
            for col_idx, (_, key, _) in enumerate(COLUMNS):
                val = r.get(key, "")
                text = self._format(key, val)
                item = QStandardItem(text)
                item.setTextAlignment(Qt.AlignCenter if key != "title" and key != "snapshot_at" else Qt.AlignLeft | Qt.AlignVCenter)
                self._paint_by_value(item, key, val, r)
                items.append(item)
            self._model.appendRow(items)

    def append_row(self, r: Dict[str, Any]):
        items = []
        for col_idx, (_, key, _) in enumerate(COLUMNS):
            val = r.get(key, "")
            text = self._format(key, val)
            item = QStandardItem(text)
            item.setTextAlignment(Qt.AlignCenter if key != "title" and key != "snapshot_at" else Qt.AlignLeft | Qt.AlignVCenter)
            self._paint_by_value(item, key, val, r)
            items.append(item)
        self._model.insertRow(0, items)

    @staticmethod
    def _format(key, val) -> str:
        if key == "is_lot":
            return "打包" if val else "单品"
        if key == "profit_rate":
            return f"{val * 100:.1f}%"
        if isinstance(val, float):
            return f"{val:.0f}"
        return str(val)

    @staticmethod
    def _paint_by_value(item: QStandardItem, key, val, row: Dict[str, Any]):
        if key == "profit_rate":
            if val >= 0.50:
                item.setForeground(QBrush(QColor("#dc2626")))
                f = item.font()
                f.setBold(True)
                item.setFont(f)
            elif val >= 0.30:
                item.setForeground(QBrush(QColor("#ea580c")))
            elif val >= 0.20:
                item.setForeground(QBrush(QColor("#ca8a04")))
            else:
                item.setForeground(QBrush(QColor("#64748b")))
        elif key == "net_profit":
            if val >= 100:
                item.setForeground(QBrush(QColor("#dc2626")))
            elif val >= 50:
                item.setForeground(QBrush(QColor("#ea580c")))
            elif val >= 30:
                item.setForeground(QBrush(QColor("#059669")))
