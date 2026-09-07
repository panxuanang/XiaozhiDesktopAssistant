from __future__ import annotations

import logging
from dataclasses import fields

from PySide6.QtCore import QObject, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFormLayout, QGroupBox, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QMessageBox, QPushButton, QSystemTrayIcon,
    QTabWidget, QTextEdit, QVBoxLayout, QWidget
)
from PySide6.QtGui import QIcon

from ..action_log import recent
from ..autostart import set_windows_autostart
from ..config import PROVIDER_PRESETS, AppSettings, load_settings, save_settings
from ..diagnostics import run_diagnostics
from ..gateway import McpGateway
from ..llm import AIClient
from ..secrets_store import get_api_key, set_api_key

logger = logging.getLogger(__name__)


class GatewaySignals(QObject):
    status = Signal(str)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("小智电脑助手")
        self.resize(760, 680)
        self.settings = load_settings()
        self.gateway: McpGateway | None = None
        self.signals = GatewaySignals()
        self.signals.status.connect(self._set_status)
        self._build_ui()
        self._load_values()
        self._build_tray()
        if self.settings.auto_connect and self.settings.xiaozhi_endpoint:
            self.start_gateway()

    def _build_ui(self):
        tabs = QTabWidget()
        self.setCentralWidget(tabs)
        tabs.addTab(self._connection_tab(), "连接")
        tabs.addTab(self._ai_tab(), "AI API")
        tabs.addTab(self._modules_tab(), "功能")
        tabs.addTab(self._diagnostics_tab(), "诊断/日志")

    def _connection_tab(self):
        w = QWidget(); layout = QVBoxLayout(w)
        box = QGroupBox("小智 MCP 连接"); form = QFormLayout(box)
        self.endpoint = QLineEdit(); self.endpoint.setPlaceholderText("wss://...token=...")
        self.status_label = QLabel("未连接")
        self.auto_connect = QCheckBox("启动软件后自动连接")
        self.auto_start = QCheckBox("Windows 登录后自动启动")
        self.start_minimized = QCheckBox("开机启动时最小化到托盘")
        form.addRow("MCP 接入地址", self.endpoint)
        form.addRow("状态", self.status_label)
        form.addRow("", self.auto_connect)
        form.addRow("", self.auto_start)
        form.addRow("", self.start_minimized)
        layout.addWidget(box)
        buttons = QHBoxLayout()
        save = QPushButton("保存设置"); save.clicked.connect(self.save)
        connect = QPushButton("连接/重连"); connect.clicked.connect(self.start_gateway)
        stop = QPushButton("停止连接"); stop.clicked.connect(self.stop_gateway)
        buttons.addWidget(save); buttons.addWidget(connect); buttons.addWidget(stop)
        layout.addLayout(buttons); layout.addStretch(1)
        return w

    def _ai_tab(self):
        w = QWidget(); layout = QVBoxLayout(w)
        box = QGroupBox("自己的模型 API（写材料/Excel/PDF/网页总结使用）"); form = QFormLayout(box)
        self.provider = QComboBox(); self.provider.addItems(PROVIDER_PRESETS.keys()); self.provider.currentTextChanged.connect(self._provider_changed)
        self.base_url = QLineEdit(); self.model = QLineEdit()
        self.api_key = QLineEdit(); self.api_key.setEchoMode(QLineEdit.Password)
        self.api_mode = QComboBox(); self.api_mode.addItems(["auto", "responses", "chat"])
        form.addRow("供应商", self.provider); form.addRow("Base URL", self.base_url); form.addRow("API Key", self.api_key); form.addRow("模型", self.model); form.addRow("接口模式", self.api_mode)
        layout.addWidget(box)
        row = QHBoxLayout(); save = QPushButton("保存 API"); save.clicked.connect(self.save); test = QPushButton("测试连接"); test.clicked.connect(self.test_api)
        row.addWidget(save); row.addWidget(test); layout.addLayout(row)
        note = QLabel("OpenAI / DeepSeek / 豆包方舟提供预设；模型名称可自行修改。auto 会优先 Responses API，不兼容时自动回退 Chat Completions。")
        note.setWordWrap(True); layout.addWidget(note); layout.addStretch(1)
        return w

    def _modules_tab(self):
        w = QWidget(); layout = QVBoxLayout(w)
        self.module_checks = {}
        labels = {
            "files":"文件助手", "office":"Word / Excel", "pdf":"PDF", "browser":"网页自动化/总结",
            "windows":"Windows UI Automation/窗口", "wechat":"微信助手", "ocr":"本地 OCR 兜底",
            "screen":"截图/视觉分析", "system":"系统状态/音量/命令"
        }
        for key, label in labels.items():
            cb = QCheckBox(label); self.module_checks[key] = cb; layout.addWidget(cb)
        warn = QLabel("安全策略：删除文件、执行命令、发送微信均设计为先确认再执行。修改功能开关后请重连 MCP。")
        warn.setWordWrap(True); layout.addWidget(warn)
        btn = QPushButton("保存并重连"); btn.clicked.connect(self.save_and_restart); layout.addWidget(btn); layout.addStretch(1)
        return w

    def _diagnostics_tab(self):
        w = QWidget(); layout = QVBoxLayout(w)
        self.diag_text = QTextEdit(); self.diag_text.setReadOnly(True)
        row = QHBoxLayout(); run = QPushButton("一键自检"); run.clicked.connect(self.run_diag); logs = QPushButton("刷新操作记录"); logs.clicked.connect(self.show_logs)
        row.addWidget(run); row.addWidget(logs); layout.addLayout(row); layout.addWidget(self.diag_text)
        return w

    def _load_values(self):
        s = self.settings
        self.endpoint.setText(s.xiaozhi_endpoint)
        self.auto_connect.setChecked(s.auto_connect); self.auto_start.setChecked(s.auto_start_windows); self.start_minimized.setChecked(s.start_minimized)
        idx = self.provider.findText(s.ai.provider); self.provider.setCurrentIndex(max(0, idx))
        self.base_url.setText(s.ai.base_url); self.model.setText(s.ai.model); self.api_key.setText(get_api_key())
        idx = self.api_mode.findText(s.ai.api_mode); self.api_mode.setCurrentIndex(max(0, idx))
        for key, cb in self.module_checks.items(): cb.setChecked(bool(getattr(s.modules, key)))

    def _provider_changed(self, name: str):
        preset = PROVIDER_PRESETS.get(name, {})
        if name != "自定义兼容API":
            self.base_url.setText(preset.get("base_url", "")); self.model.setText(preset.get("model", ""))

    def save(self):
        s = self.settings
        s.xiaozhi_endpoint = self.endpoint.text().strip(); s.auto_connect = self.auto_connect.isChecked(); s.auto_start_windows = self.auto_start.isChecked(); s.start_minimized = self.start_minimized.isChecked()
        s.ai.provider = self.provider.currentText(); s.ai.base_url = self.base_url.text().strip(); s.ai.model = self.model.text().strip(); s.ai.api_mode = self.api_mode.currentText()
        for key, cb in self.module_checks.items(): setattr(s.modules, key, cb.isChecked())
        save_settings(s); set_api_key(self.api_key.text()); set_windows_autostart(s.auto_start_windows)
        self.settings = s
        QMessageBox.information(self, "保存", "设置已保存。API Key 已使用 Windows DPAPI 加密存储。")

    def save_and_restart(self):
        self.save(); self.start_gateway()

    def test_api(self):
        try:
            self.save(); answer = AIClient().test(); QMessageBox.information(self, "API 测试", f"连接成功：{answer}")
        except Exception as exc:
            QMessageBox.critical(self, "API 测试失败", str(exc))

    def start_gateway(self):
        endpoint = self.endpoint.text().strip()
        if not endpoint.startswith(("ws://", "wss://")):
            QMessageBox.warning(self, "MCP 地址", "请先填写以 ws:// 或 wss:// 开头的小智 MCP 接入地址。")
            return
        self.stop_gateway()
        self.gateway = McpGateway(endpoint, on_status=self.signals.status.emit); self.gateway.start()

    def stop_gateway(self):
        if self.gateway:
            self.gateway.stop(); self.gateway = None

    def _set_status(self, text: str):
        self.status_label.setText(text)
        if hasattr(self, "tray"):
            self.tray.setToolTip(f"小智电脑助手 · {text}")

    def run_diag(self):
        lines = []
        for name, ok, detail in run_diagnostics():
            lines.append(f"{'✅' if ok else '❌'} {name}: {detail}")
        self.diag_text.setPlainText("\n".join(lines))

    def show_logs(self):
        rows = recent(100)
        self.diag_text.setPlainText("\n".join(f"{r['ts']} [{r['status']}] {r['action']} {r['detail']}" for r in rows))

    def _build_tray(self):
        self.tray = QSystemTrayIcon(self)
        self.tray.setToolTip("小智电脑助手")
        menu = __import__("PySide6.QtWidgets", fromlist=["QMenu"]).QMenu()
        show = QAction("打开设置", self); show.triggered.connect(self.show_normal)
        reconnect = QAction("重新连接", self); reconnect.triggered.connect(self.start_gateway)
        pause = QAction("暂停连接", self); pause.triggered.connect(self.stop_gateway)
        quit_action = QAction("退出", self); quit_action.triggered.connect(self.quit_app)
        menu.addAction(show); menu.addAction(reconnect); menu.addAction(pause); menu.addSeparator(); menu.addAction(quit_action)
        self.tray.setContextMenu(menu); self.tray.activated.connect(lambda reason: self.show_normal() if reason == QSystemTrayIcon.DoubleClick else None); self.tray.show()

    def show_normal(self):
        self.show(); self.raise_(); self.activateWindow()

    def closeEvent(self, event):
        event.ignore(); self.hide(); self.tray.showMessage("小智电脑助手", "程序仍在后台运行，可从托盘打开。", QSystemTrayIcon.Information, 2000)

    def quit_app(self):
        self.stop_gateway(); self.tray.hide(); QApplication.quit()
