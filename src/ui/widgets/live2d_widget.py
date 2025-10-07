import os
import traceback
from PyQt5 import QtCore
from PyQt5.QtWidgets import QOpenGLWidget

from src.controllers.live2d_controller import Live2DController
from PyQt5 import QtWidgets


class Live2DWidget(QOpenGLWidget):
    def __init__(self, controller: Live2DController, parent=None):
        super().__init__(parent)
        self.controller = controller
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(round(1000 / 60))

        # Accept mouse events for interaction
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
        self.setMouseTracking(True)

        # Make the widget background transparent
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setAutoFillBackground(False)
    # 已移除“穿透”自动检测与防抖逻辑

    def initializeGL(self):
        try:
            # Initialize live2d in GL context
            self.controller.initialize_gl()
            self.controller.load_model_if_needed()
        except Exception:
            print('Exception during widget initializeGL:')
            traceback.print_exc()

    def resizeGL(self, w: int, h: int):
        try:
            self.controller.resize(w, h)
        except Exception:
            traceback.print_exc()

    def paintGL(self):
        try:
            # clear buffer with transparent background if live2d exposes clearBuffer
            try:
                from OpenGL.GL import glClearColor, GL_COLOR_BUFFER_BIT, GL_DEPTH_BUFFER_BIT, glClear
                glClearColor(0.0, 0.0, 0.0, 0.0)
                glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
            except Exception:
                pass
            self.controller.update_and_draw()
        except Exception:
            print('Exception during paintGL:')
            traceback.print_exc()

    def closeEvent(self, event):
        try:
            self.controller.dispose()
        except Exception:
            traceback.print_exc()
        return super().closeEvent(event)

    def mousePressEvent(self, event):
        # on click, dispatch to colliders first; if none, trigger a random motion
        try:
            gpos = self.mapToGlobal(event.pos())
            handled = self.controller.handle_click(gpos.x(), gpos.y())
            # if no collider handled this click, fallback to random motion
            if not handled:
                self.controller.start_random_motion()
        except Exception:
            traceback.print_exc()

    def mouseMoveEvent(self, event):
        # translate mouse position to widget coordinates and pass to model
        try:
            x = event.x()
            y = event.y()
            # pass coordinates to controller/manager
            self.controller.drag(x, y)
            # 已移除“穿透”自动检测逻辑
        except Exception:
            traceback.print_exc()

    # 已移除：应用“穿透”状态的方法
