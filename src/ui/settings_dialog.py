"""参数设置对话框。"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QFormLayout, QDialogButtonBox, QDoubleSpinBox, QCheckBox, QSpinBox,
    QVBoxLayout,
)

from config import (
    DEFAULT_PROFIT_RATE_THRESHOLD,
    DEFAULT_PROFIT_AMOUNT_THRESHOLD,
)
from src.services.scan_service import ScanOptions


class SettingsDialog(QDialog):
    def __init__(self, opts: ScanOptions, parent=None):
        super().__init__(parent)
        self.setWindowTitle("扫描参数设置")
        self.resize(360, 240)
        self._opts = opts

        form = QFormLayout()

        self.rate_spin = QDoubleSpinBox()
        self.rate_spin.setRange(0, 1.0)
        self.rate_spin.setSingleStep(0.01)
        self.rate_spin.setDecimals(2)
        self.rate_spin.setSuffix("  (利润率 ≥)")
        self.rate_spin.setValue(opts.profit_rate_threshold)
        form.addRow("双阈值 · 利润率", self.rate_spin)

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0, 10_000)
        self.amount_spin.setSingleStep(5)
        self.amount_spin.setSuffix("  元 (毛利 ≥)")
        self.amount_spin.setValue(opts.profit_amount_threshold)
        form.addRow("双阈值 · 绝对毛利", self.amount_spin)

        self.items_spin = QSpinBox()
        self.items_spin.setRange(1, 50)
        self.items_spin.setSuffix("  件/关键词")
        self.items_spin.setValue(opts.max_items_per_keyword)
        form.addRow("每关键词抓取数量", self.items_spin)

        self.push_cb = QCheckBox("达标时推送桌面通知")
        self.push_cb.setChecked(opts.push_desktop)
        form.addRow("推送", self.push_cb)

        self.only_passed_cb = QCheckBox("表格只显示通过阈值的")
        self.only_passed_cb.setChecked(opts.only_show_passed)
        form.addRow("展示", self.only_passed_cb)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addStretch(1)
        layout.addWidget(buttons)

    def get_options(self) -> ScanOptions:
        return ScanOptions(
            profit_rate_threshold=float(self.rate_spin.value()),
            profit_amount_threshold=float(self.amount_spin.value()),
            max_items_per_keyword=int(self.items_spin.value()),
            push_desktop=self.push_cb.isChecked(),
            only_show_passed=self.only_passed_cb.isChecked(),
        )
