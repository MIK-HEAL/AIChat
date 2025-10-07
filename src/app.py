import sys
from PyQt5 import QtWidgets, QtCore

from src.controllers.live2d_controller import Live2DController
from src.services.chat_manager import ChatManager
from src.services.vision_service import ScreenVisionService
from src.ui.widgets.live2d_widget_clean import Live2DWidget
from src.ui.dialogs import SettingsDialog, ChatDialog
# Note: no state is used here anymore


def main():
    app = QtWidgets.QApplication(sys.argv)
    controller = Live2DController()
    chat_manager = ChatManager(controller)
    vision_service = ScreenVisionService()
    chat_manager.attach_vision_service(vision_service)
    widget = Live2DWidget(controller)
    widget.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

    # Create a frameless, transparent, always-on-top window to act like a desktop pet
    window = QtWidgets.QMainWindow()

    central = QtWidgets.QWidget()
    central.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
    central.setAutoFillBackground(False)
    window.setCentralWidget(central)

    layout = QtWidgets.QVBoxLayout(central)
    layout.setContentsMargins(12, 12, 12, 12)
    layout.setSpacing(10)

    control_bar = QtWidgets.QFrame()
    control_bar.setObjectName('controlBar')
    control_bar.setAttribute(QtCore.Qt.WA_StyledBackground, True)
    control_bar.setStyleSheet(
        """
        #controlBar {
            background-color: rgba(24, 24, 24, 0.7);
            border-radius: 10px;
        }
        #controlBar QPushButton {
            color: white;
            background-color: rgba(255, 255, 255, 0.12);
            border: 1px solid rgba(255, 255, 255, 0.3);
            border-radius: 8px;
            padding: 6px 16px;
            font-weight: 500;
        }
        #controlBar QPushButton:hover {
            background-color: rgba(255, 255, 255, 0.25);
        }
        #controlBar QPushButton:pressed {
            background-color: rgba(255, 255, 255, 0.32);
        }
        """
    )
    control_layout = QtWidgets.QHBoxLayout(control_bar)
    control_layout.setContentsMargins(10, 10, 10, 10)
    control_layout.setSpacing(8)

    settings_button = QtWidgets.QPushButton('设置')
    dialog_button = QtWidgets.QPushButton('对话')

    control_layout.addWidget(settings_button)
    control_layout.addWidget(dialog_button)
    control_layout.addStretch(1)

    layout.addWidget(control_bar, 0, QtCore.Qt.AlignTop)
    layout.addWidget(widget, 1)

    def open_settings_dialog():
        dialog = SettingsDialog(window)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            chat_manager.reload_config()

    def open_chat_dialog():
        existing = getattr(window, '_chat_dialog', None)
        if existing is None or not existing.isVisible():
            dialog = ChatDialog(chat_manager, window)
            dialog.setWindowModality(QtCore.Qt.NonModal)

            def _clear_reference():
                try:
                    delattr(window, '_chat_dialog')
                except AttributeError:
                    pass

            dialog.destroyed.connect(lambda *_: _clear_reference())
            window._chat_dialog = dialog
        else:
            dialog = existing

        dialog.show()
        dialog.raise_()
        dialog.activateWindow()

    settings_button.clicked.connect(open_settings_dialog)
    dialog_button.clicked.connect(open_chat_dialog)

    def flush_pending_commands() -> None:
        commands = chat_manager.drain_pending_commands()
        if commands:
            chat_manager.apply_commands(commands)

    command_timer = QtCore.QTimer(window)
    command_timer.setInterval(500)
    command_timer.timeout.connect(flush_pending_commands)
    command_timer.start()

    vision_service.start()

    window.setWindowFlags(window.windowFlags() | QtCore.Qt.FramelessWindowHint | QtCore.Qt.WindowStaysOnTopHint)
    window.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)

    # Use a smaller window initially; user can drag/resize it
    window.resize(480, 560)
    # center to screen
    screen = app.primaryScreen()
    rect = screen.availableGeometry()
    x = rect.x() + (rect.width() - window.width()) // 2
    y = rect.y() + (rect.height() - window.height()) // 2
    window.move(x, y)

    # Note: 已移除“穿透”功能（状态标签、快捷键、窗口样式切换），恢复为普通可交互窗口

    def _cleanup() -> None:
        command_timer.stop()
        vision_service.stop()

    app.aboutToQuit.connect(_cleanup)

    window.show()
    return app.exec_()


if __name__ == '__main__':
    sys.exit(main())
