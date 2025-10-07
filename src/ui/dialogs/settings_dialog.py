from __future__ import annotations

from typing import Dict

from PyQt5 import QtCore, QtWidgets

from src.utils import storage
from src.services.vision import VisionConfig, load_config as load_vision_config, save_config as save_vision_config


class SettingsDialog(QtWidgets.QDialog):
    """编辑用户配置与 AI 提示词。"""

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setWindowTitle("设置")
        self.setModal(True)
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.resize(480, 400)

        self._user_data: Dict[str, str] = storage.load_user_settings()
        self._ai_data: Dict[str, str] = storage.load_ai_prompts()
        self._vision_config: VisionConfig = load_vision_config()

        self._build_ui()
        self._bind_data()

    def _build_ui(self) -> None:
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setDocumentMode(True)
        main_layout.addWidget(self.tabs, 1)

        # 用户/连接设置
        general_tab = QtWidgets.QWidget()
        general_layout = QtWidgets.QFormLayout(general_tab)
        general_layout.setLabelAlignment(QtCore.Qt.AlignRight)
        general_layout.setVerticalSpacing(12)

        self.display_name_edit = QtWidgets.QLineEdit()
        self.api_url_edit = QtWidgets.QLineEdit()
        self.api_key_edit = QtWidgets.QLineEdit()
        self.api_key_edit.setEchoMode(QtWidgets.QLineEdit.Password)
        self.model_edit = QtWidgets.QLineEdit()

        general_layout.addRow("显示昵称", self.display_name_edit)
        general_layout.addRow("接口地址", self.api_url_edit)
        general_layout.addRow("接口密钥", self.api_key_edit)
        general_layout.addRow("模型名称", self.model_edit)

        self.tabs.addTab(general_tab, "连接")

        # 提示词设置
        prompt_tab = QtWidgets.QWidget()
        prompt_layout = QtWidgets.QFormLayout(prompt_tab)
        prompt_layout.setLabelAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTop)
        prompt_layout.setVerticalSpacing(12)

        self.system_prompt_edit = QtWidgets.QPlainTextEdit()
        self.system_prompt_edit.setPlaceholderText("系统提示词，描述桌宠的行为与身份…")
        self.system_prompt_edit.setMinimumHeight(120)

        self.greeting_edit = QtWidgets.QPlainTextEdit()
        self.greeting_edit.setPlaceholderText("当桌宠开始对话时的问候语…")
        self.greeting_edit.setMaximumHeight(120)

        prompt_layout.addRow("系统提示词", self.system_prompt_edit)
        prompt_layout.addRow("欢迎语", self.greeting_edit)

        self.tabs.addTab(prompt_tab, "提示词")

        # 视觉设置
        vision_tab = QtWidgets.QWidget()
        vision_layout = QtWidgets.QVBoxLayout(vision_tab)
        vision_layout.setContentsMargins(12, 12, 12, 12)
        vision_layout.setSpacing(12)

        self.vision_enable_checkbox = QtWidgets.QCheckBox("启用视觉捕获（定时截图并发送给 AI）")
        vision_layout.addWidget(self.vision_enable_checkbox)

        interval_layout = QtWidgets.QHBoxLayout()
        interval_layout.addWidget(QtWidgets.QLabel("截图间隔（秒）"))
        self.capture_interval_spin = QtWidgets.QDoubleSpinBox()
        self.capture_interval_spin.setRange(1.0, 3600.0)
        self.capture_interval_spin.setDecimals(1)
        self.capture_interval_spin.setSingleStep(0.5)
        interval_layout.addWidget(self.capture_interval_spin, 1)
        vision_layout.addLayout(interval_layout)

        region_group = QtWidgets.QGroupBox("截取区域（留空代表全屏）")
        region_layout = QtWidgets.QGridLayout(region_group)
        region_layout.setContentsMargins(12, 12, 12, 12)
        region_layout.setHorizontalSpacing(10)
        region_layout.setVerticalSpacing(8)

        self.region_enable_checkbox = QtWidgets.QCheckBox("使用自定义区域")
        region_layout.addWidget(self.region_enable_checkbox, 0, 0, 1, 4)

        region_layout.addWidget(QtWidgets.QLabel("左上角 X"), 1, 0)
        self.region_left_spin = QtWidgets.QSpinBox()
        self.region_left_spin.setRange(0, 10000)
        region_layout.addWidget(self.region_left_spin, 1, 1)

        region_layout.addWidget(QtWidgets.QLabel("左上角 Y"), 1, 2)
        self.region_top_spin = QtWidgets.QSpinBox()
        self.region_top_spin.setRange(0, 10000)
        region_layout.addWidget(self.region_top_spin, 1, 3)

        region_layout.addWidget(QtWidgets.QLabel("宽度"), 2, 0)
        self.region_width_spin = QtWidgets.QSpinBox()
        self.region_width_spin.setRange(0, 10000)
        region_layout.addWidget(self.region_width_spin, 2, 1)

        region_layout.addWidget(QtWidgets.QLabel("高度"), 2, 2)
        self.region_height_spin = QtWidgets.QSpinBox()
        self.region_height_spin.setRange(0, 10000)
        region_layout.addWidget(self.region_height_spin, 2, 3)

        vision_layout.addWidget(region_group)

        ocr_group = QtWidgets.QGroupBox("文字识别")
        ocr_layout = QtWidgets.QFormLayout(ocr_group)
        ocr_layout.setLabelAlignment(QtCore.Qt.AlignRight)
        ocr_layout.setVerticalSpacing(10)

        self.ocr_enable_checkbox = QtWidgets.QCheckBox("启用 OCR 文本提取")
        ocr_layout.addRow("开启 OCR", self.ocr_enable_checkbox)

        self.ocr_language_edit = QtWidgets.QLineEdit()
        self.ocr_language_edit.setPlaceholderText("如：chi_sim+eng")
        ocr_layout.addRow("语言包", self.ocr_language_edit)

        self.history_limit_spin = QtWidgets.QSpinBox()
        self.history_limit_spin.setRange(1, 50)
        ocr_layout.addRow("保留历史条数", self.history_limit_spin)

        vision_layout.addWidget(ocr_group)
        vision_layout.addStretch(1)

        self.tabs.addTab(vision_tab, "视觉")

        self.region_enable_checkbox.stateChanged.connect(self._on_region_toggle)

        # 底部按钮
        self.button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        self.button_box.accepted.connect(self._on_accept)
        self.button_box.rejected.connect(self.reject)
        main_layout.addWidget(self.button_box, 0, QtCore.Qt.AlignRight)

    def _bind_data(self) -> None:
        self.display_name_edit.setText(self._user_data.get("display_name", ""))
        self.api_url_edit.setText(self._user_data.get("api_url", ""))
        self.api_key_edit.setText(self._user_data.get("api_key", ""))
        self.model_edit.setText(self._user_data.get("model", ""))

        self.system_prompt_edit.setPlainText(self._ai_data.get("system_prompt", ""))
        self.greeting_edit.setPlainText(self._ai_data.get("greeting", ""))
        self.vision_enable_checkbox.setChecked(self._vision_config.enabled)
        self.capture_interval_spin.setValue(max(1.0, float(self._vision_config.capture_interval)))
        region = self._vision_config.region or {}
        use_region = isinstance(region, dict) and all(key in region for key in ("left", "top", "width", "height"))
        self.region_enable_checkbox.setChecked(use_region)
        self.region_left_spin.setValue(int(region.get("left", 0)) if use_region else 0)
        self.region_top_spin.setValue(int(region.get("top", 0)) if use_region else 0)
        self.region_width_spin.setValue(int(region.get("width", 0)) if use_region else 0)
        self.region_height_spin.setValue(int(region.get("height", 0)) if use_region else 0)
        self.ocr_enable_checkbox.setChecked(self._vision_config.ocr_enabled)
        self.ocr_language_edit.setText(self._vision_config.ocr_language)
        self.history_limit_spin.setValue(int(self._vision_config.max_history))
        self._on_region_toggle(self.region_enable_checkbox.checkState())

    def _on_accept(self) -> None:
        updated_user = {
            "display_name": self.display_name_edit.text().strip(),
            "api_url": self.api_url_edit.text().strip(),
            "api_key": self.api_key_edit.text().strip(),
            "model": self.model_edit.text().strip(),
        }
        updated_ai = {
            "system_prompt": self.system_prompt_edit.toPlainText().strip(),
            "greeting": self.greeting_edit.toPlainText().strip(),
        }

        self._user_data = storage.save_user_settings(updated_user)
        self._ai_data = storage.save_ai_prompts(updated_ai)

        if self.region_enable_checkbox.isChecked():
            region = {
                "left": int(self.region_left_spin.value()),
                "top": int(self.region_top_spin.value()),
                "width": int(self.region_width_spin.value()),
                "height": int(self.region_height_spin.value()),
            }
            if region["width"] <= 0 or region["height"] <= 0:
                region = None
        else:
            region = None

        vision_cfg = VisionConfig(
            enabled=self.vision_enable_checkbox.isChecked(),
            capture_interval=float(self.capture_interval_spin.value()),
            region=region,
            ocr_enabled=self.ocr_enable_checkbox.isChecked(),
            ocr_language=self.ocr_language_edit.text().strip() or "chi_sim+eng",
            max_history=int(self.history_limit_spin.value()),
        )
        save_vision_config(vision_cfg)
        self._vision_config = vision_cfg

        QtWidgets.QMessageBox.information(self, "保存成功", "配置已保存。")
        self.accept()

    def _on_region_toggle(self, state: int) -> None:
        enabled = state == QtCore.Qt.Checked
        for widget in (
            self.region_left_spin,
            self.region_top_spin,
            self.region_width_spin,
            self.region_height_spin,
        ):
            widget.setEnabled(enabled)

    @property
    def user_settings(self) -> Dict[str, str]:
        return self._user_data

    @property
    def ai_prompts(self) -> Dict[str, str]:
        return self._ai_data
