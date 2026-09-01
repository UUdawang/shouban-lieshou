"""主窗口。"""
from __future__ import annotations

import datetime as dt
from typing import Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QToolBar, QPlainTextEdit,
    QProgressBar, QStatusBar, QTabWidget, QLabel, QMessageBox, QSystemTrayIcon,
    QMenu, QStyle,
)

from src.models import candidate_model, auction_watch_model
from src.services.scan_service import ScanOptions, ScanService, ScanSummary
from src.ui.widgets import CandidateTable
from src.ui.settings_dialog import SettingsDialog
from src.ui.auction_watch_panel import AuctionWatchPanel
from src.notifier import notifier, PushMessage


# ============================================================
# 后台扫描线程：避免 UI 卡顿
# ============================================================
class ScanWorker(QThread):
    stage_changed = Signal(str, int, int)       # stage, current, total
    summary_ready = Signal(object)              # ScanSummary
    error_occurred = Signal(str)

    def __init__(self, service: ScanService, opts: ScanOptions):
        super().__init__()
        self._service = service
        self._opts = opts

    def run(self):
        try:
            def cb(stage, cur, total):
                self.stage_changed.emit(stage, cur, total)
            self._service.on_progress(cb)
            summary = self._service.run_scan(self._opts)
            self.summary_ready.emit(summary)
        except Exception as e:
            self.error_occurred.emit(str(e))


# ============================================================
# 主窗口
# ============================================================
class MainWindow(QMainWindow):
    def __init__(self, opts: Optional[ScanOptions] = None):
        super().__init__()
        self.setWindowTitle("手办套利监控 MVP-0")
        self.resize(1200, 720)

        self._opts = opts or ScanOptions()
        self._scan_service = ScanService()
        self._worker: Optional[ScanWorker] = None

        self._build_ui()
        self._build_toolbar()
        self._build_tray()

        # 日志+桌面通知双管齐下
        notifier.add_fallback(self._log_from_push)

        self._refresh_candidates()
        self._refresh_auctions()
        self._log("就绪。点击「开始扫描」或调整「设置」开始。")

    # ---------- UI 构建 ----------
    def _build_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(10, 10, 10, 10)
        outer.setSpacing(8)

        # 顶部: 摘要条
        self.summary_label = QLabel("上次扫描：暂无")
        self.summary_label.setStyleSheet("font-size:13px; color:#52525b; padding: 4px 2px;")
        outer.addWidget(self.summary_label)

        # Tabs
        self.tabs = QTabWidget()
        self.candidate_table = CandidateTable()
        self.tabs.addTab(self.candidate_table, "候选商品 (达标的套利机会)")
        self.auction_panel = AuctionWatchPanel()
        self.tabs.addTab(self.auction_panel, "盯拍拍卖")
        outer.addWidget(self.tabs, 1)

        # 日志
        self.log_view = QPlainTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumBlockCount(500)
        self.log_view.setStyleSheet("background:#fafafa; font-family: Consolas, 'Courier New', monospace; font-size:12px;")
        outer.addWidget(self.log_view, 1)

        # 进度条
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        outer.addWidget(self.progress)

        sb = QStatusBar(self)
        self.setStatusBar(sb)
        sb.showMessage("MVP-0 · Mock数据模式 · 挖煤姬 + 闲鱼")

    def _build_toolbar(self):
        tb = QToolBar("主工具栏", self)
        tb.setMovable(False)
        self.addToolBar(tb)

        style = self.style()
        self.act_scan = QAction(style.standardIcon(QStyle.SP_BrowserReload), "开始扫描", self)
        self.act_scan.triggered.connect(self._on_start_scan)
        tb.addAction(self.act_scan)

        tb.addSeparator()
        self.act_refresh = QAction(style.standardIcon(QStyle.SP_DirOpenIcon), "刷新列表", self)
        self.act_refresh.triggered.connect(self._on_refresh_all)
        tb.addAction(self.act_refresh)

        self.act_settings = QAction(style.standardIcon(QStyle.SP_FileDialogDetailedView), "设置", self)
        self.act_settings.triggered.connect(self._on_settings)
        tb.addAction(self.act_settings)

    def _build_tray(self):
        style = self.style()
        icon = style.standardIcon(QStyle.SP_MessageBoxInformation)
        self.tray = QSystemTrayIcon(icon, self)
        self.tray.setToolTip("手办套利监控")
        menu = QMenu()
        menu.addAction("显示主窗口", self.showNormal)
        menu.addAction("开始扫描", self._on_start_scan)
        menu.addSeparator()
        menu.addAction("退出", self.close)
        self.tray.setContextMenu(menu)
        self.tray.show()
        # 把托盘注入 notifier，这样 notifier.push 时就能调用 showMessage
        notifier.bind_tray(self.tray)
        self.tray.activated.connect(self._on_tray_activated)

    def _on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.showNormal()

    def closeEvent(self, event):
        # 关闭最小化到托盘，避免忘记开监控
        if self.tray.isVisible():
            self.hide()
            self.tray.showMessage(
                "手办套利监控",
                "已最小化到系统托盘，继续后台监控。",
                QSystemTrayIcon.Information,
                2500,
            )
            event.ignore()
        else:
            event.accept()

    # ---------- 操作 ----------
    def _on_settings(self):
        dlg = SettingsDialog(self._opts, self)
        if dlg.exec():
            self._opts = dlg.get_options()
            self._log(
                f"参数已更新：利润率≥{self._opts.profit_rate_threshold*100:.0f}% "
                f"且毛利≥{self._opts.profit_amount_threshold:.0f}元"
            )

    def _on_start_scan(self):
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "扫描中", "已有扫描在跑，请等待完成。")
            return
        self._log(f"开始扫描：利润率≥{self._opts.profit_rate_threshold*100:.0f}%，毛利≥{self._opts.profit_amount_threshold:.0f}元")
        self.progress.setValue(0)
        self.act_scan.setEnabled(False)
        self._worker = ScanWorker(self._scan_service, self._opts)
        self._worker.stage_changed.connect(self._on_stage)
        self._worker.summary_ready.connect(self._on_summary)
        self._worker.error_occurred.connect(self._on_scan_error)
        self._worker.finished.connect(lambda: self.act_scan.setEnabled(True))
        self._worker.start()

    def _on_stage(self, stage: str, current: int, total: int):
        if total <= 0:
            return
        pct = int(current / max(1, total) * 100)
        self.progress.setValue(pct)
        self.statusBar().showMessage(f"{stage}：{current} / {total}", 3000)

    def _on_summary(self, summary: ScanSummary):
        self.progress.setValue(100)
        lines = [
            f"扫描结束：共抓到{summary.total_raw_items}条 → 计算{summary.calculated}条",
            f" → 打包{summary.lot_items}件，达标{summary.passed_threshold}条。",
        ]
        self._log("".join(lines))
        if summary.errors:
            self._log(f"  错误 {len(summary.errors)} 条：")
            for e in summary.errors[:5]:
                self._log(f"    - {e}")
        # 把新达标的追加到表格顶部
        for r in summary.results:
            self.candidate_table.append_row(r.to_candidate_dict())
        self._refresh_candidates(load_all=False, only_count_update=True)
        self._refresh_auctions()
        self.summary_label.setText(
            f"上次扫描 {dt.datetime.now().strftime('%H:%M:%S')} · 达标{summary.passed_threshold}条 · "
            f"利润率≥{self._opts.profit_rate_threshold*100:.0f}% 且毛利≥{self._opts.profit_amount_threshold:.0f}元"
        )
        if summary.passed_threshold == 0 and summary.calculated > 0:
            self._log("（注：当前阈值太高，没有达标的机会。可以在「设置」里降低阈值再跑一次）")

    def _on_scan_error(self, msg: str):
        self._log(f"扫描出错: {msg}")
        self.progress.setValue(0)

    def _on_refresh_all(self):
        self._refresh_candidates()
        self._refresh_auctions()

    def _refresh_candidates(self, load_all: bool = True, only_count_update: bool = False):
        rows = candidate_model.list_candidates(
            limit=500,
            passed_only=self._opts.only_show_passed,
        )
        if load_all and not only_count_update:
            self.candidate_table.load_rows(rows)

    def _refresh_auctions(self):
        rows = auction_watch_model.list_active_auctions()
        self.auction_panel.load_rows(rows)

    # ---------- 日志 ----------
    def _log(self, msg: str):
        ts = dt.datetime.now().strftime("%H:%M:%S")
        self.log_view.appendPlainText(f"[{ts}] {msg}")

    def _log_from_push(self, pm: PushMessage):
        self._log(f"[推送-{pm.level}] {pm.title} | {pm.body.split(chr(10))[0]}")
