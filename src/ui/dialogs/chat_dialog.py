from __future__ import annotations

import html
from typing import Optional, cast

from PyQt5 import QtCore, QtGui, QtWidgets

from src.services.chat_manager import ChatManager
from src.services.chat_types import ChatResponse, ChatCommand


class _ChatWorker(QtCore.QThread):
    finished_with_result = QtCore.pyqtSignal(object)
    failed = QtCore.pyqtSignal(str)

    def __init__(self, manager: ChatManager, message: str, parent: Optional[QtCore.QObject] = None):
        super().__init__(parent)
        self._manager = manager
        self._message = message

    def run(self) -> None:  # pragma: no cover - UI thread integration
        try:
            response = self._manager.send_user_message(self._message)
            self.finished_with_result.emit(response)
        except Exception as exc:  # pragma: no cover - defensively capture
            self.failed.emit(str(exc))


class ChatDialog(QtWidgets.QDialog):
    """A lightweight chat window that talks to the configured LLM endpoint."""

    def __init__(self, manager: ChatManager, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("对话")
        self.resize(520, 560)
        self.setModal(False)

        self._chat_manager = manager
        self._current_worker: Optional[_ChatWorker] = None
        self._expression_combo: Optional[QtWidgets.QComboBox] = None

        settings = manager.user_settings
        self._user_name = settings.get("display_name") or "我"
        self._assistant_name = "桌宠"

        self._build_ui()
        self._refresh_expression_options()
        self._load_history()

        greeting = manager.get_greeting()
        if greeting and not manager.get_history():
            self._append_message(self._assistant_name, greeting)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title_label = QtWidgets.QLabel("桌宠对话")
        title_label.setStyleSheet("font-size: 18px; font-weight: 600;")
        layout.addWidget(title_label)

        expression_bar = QtWidgets.QHBoxLayout()
        expression_bar.setSpacing(6)

        expression_label = QtWidgets.QLabel("表情预设")
        expression_label.setStyleSheet("font-weight: 500;")
        expression_bar.addWidget(expression_label)

        self._expression_combo = QtWidgets.QComboBox()
        self._expression_combo.setMinimumWidth(160)
        expression_bar.addWidget(self._expression_combo, 1)

        self.expression_apply_button = QtWidgets.QPushButton("应用")
        self.expression_apply_button.clicked.connect(self._on_expression_apply_clicked)
        expression_bar.addWidget(self.expression_apply_button)

        self.expression_reset_button = QtWidgets.QPushButton("复位")
        self.expression_reset_button.clicked.connect(lambda: self._apply_expression("neutral"))
        expression_bar.addWidget(self.expression_reset_button)

        layout.addLayout(expression_bar)

        self.history_view = QtWidgets.QTextBrowser()
        self.history_view.setReadOnly(True)
        self.history_view.setOpenExternalLinks(True)
        layout.addWidget(self.history_view, 1)

        self.input_edit = QtWidgets.QPlainTextEdit()
        self.input_edit.setPlaceholderText("输入消息，Ctrl+Enter 发送…")
        self.input_edit.setFixedHeight(110)
        self.input_edit.installEventFilter(self)
        layout.addWidget(self.input_edit)

        button_bar = QtWidgets.QHBoxLayout()
        self.status_label = QtWidgets.QLabel()
        self.status_label.setMinimumWidth(160)
        button_bar.addWidget(self.status_label, 1)

        self.clear_button = QtWidgets.QPushButton("清空")
        self.clear_button.clicked.connect(self._on_clear_history)
        button_bar.addWidget(self.clear_button)

        self.send_button = QtWidgets.QPushButton("发送")
        self.send_button.clicked.connect(self._on_send_clicked)
        button_bar.addWidget(self.send_button)

        layout.addLayout(button_bar)

    # ------------------------------------------------------------------
    # Event handling
    # ------------------------------------------------------------------
    def eventFilter(self, obj: QtCore.QObject, event: QtCore.QEvent) -> bool:  # noqa: N802
        if obj is self.input_edit and event.type() == QtCore.QEvent.KeyPress:
            key_event = cast(QtGui.QKeyEvent, event)
            if key_event.key() in (QtCore.Qt.Key_Return, QtCore.Qt.Key_Enter):
                if key_event.modifiers() & QtCore.Qt.ControlModifier:
                    self._on_send_clicked()
                    return True
        return super().eventFilter(obj, event)

    def _on_send_clicked(self) -> None:
        if self._current_worker is not None:
            return
        text = self.input_edit.toPlainText().strip()
        if not text:
            self.status_label.setText("请输入消息")
            return
        self.status_label.setText("正在发送…")
        self._append_message(self._user_name, text)
        self.input_edit.clear()
        self._start_worker(text)

    def _on_clear_history(self) -> None:
        if self._current_worker is not None:
            self.status_label.setText("等待当前对话完成后再清空")
            return
        self.history_view.clear()
        self._chat_manager.reset_history()
        greeting = self._chat_manager.get_greeting()
        if greeting:
            self._append_message(self._assistant_name, greeting)
        self.status_label.setText("历史已清空")

    def _start_worker(self, message: str) -> None:
        worker = _ChatWorker(self._chat_manager, message, self)
        worker.finished_with_result.connect(self._on_worker_finished)
        worker.failed.connect(self._on_worker_failed)
        worker.finished.connect(self._on_worker_cleanup)
        self._current_worker = worker
        worker.start()
        self.send_button.setEnabled(False)
        self.clear_button.setEnabled(False)

    def _on_worker_finished(self, response: ChatResponse) -> None:
        if response.is_error():
            self._append_message(self._assistant_name, response.text)
            self.status_label.setText(response.error or "对话出错")
        else:
            self._append_message(self._assistant_name, response.text)
            self.status_label.setText("")
            if response.commands:
                self._chat_manager.apply_commands(response.commands)

    def _on_worker_failed(self, message: str) -> None:
        self._append_message(self._assistant_name, f"发生错误：{message}")
        self.status_label.setText(message)

    def _on_worker_cleanup(self) -> None:
        if self._current_worker:
            self._current_worker.deleteLater()
            self._current_worker = None
        self.send_button.setEnabled(True)
        self.clear_button.setEnabled(True)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _load_history(self) -> None:
        for message in self._chat_manager.get_history():
            if message.role == "user":
                name = self._user_name
            elif message.role == "assistant":
                name = self._assistant_name
            elif message.role == "system":
                name = "视觉" if message.content.startswith("[视觉捕获]") else "系统"
            else:
                name = self._assistant_name
            self._append_message(name, message.content)

    def _append_message(self, sender: str, text: str) -> None:
        body = html.escape(text).replace("\n", "<br>")
        self.history_view.append(f"<p><b>{html.escape(sender)}：</b> {body}</p>")
        self.history_view.verticalScrollBar().setValue(self.history_view.verticalScrollBar().maximum())

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:  # pragma: no cover - UI interaction
        if self._current_worker and self._current_worker.isRunning():
            self._current_worker.wait(1000)
        return super().closeEvent(event)

    def _refresh_expression_options(self) -> None:
        if self._expression_combo is None:
            return
        names = list(self._chat_manager.list_expressions())
        self._expression_combo.clear()
        if not names:
            self._expression_combo.addItem("（未定义）", "")
            self._expression_combo.setEnabled(False)
            self.expression_apply_button.setEnabled(False)
            self.expression_reset_button.setEnabled(False)
        else:
            for name in names:
                self._expression_combo.addItem(name, name)
            self._expression_combo.setCurrentIndex(0)
            self._expression_combo.setEnabled(True)
            self.expression_apply_button.setEnabled(True)
            self.expression_reset_button.setEnabled(True)

    def _on_expression_apply_clicked(self) -> None:
        if self._expression_combo is None:
            return
        name = self._expression_combo.currentData() or self._expression_combo.currentText()
        if isinstance(name, str) and name:
            self._apply_expression(name)

    def _apply_expression(self, name: str) -> None:
        command = ChatCommand(type="expression", payload={"name": name})
        self._chat_manager.apply_commands([command])
        self.status_label.setText(f"已应用表情：{name}")
