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
        
        # Mouse drag/resize state
        self._dragging_model = False
        self._dragging_window = False
        self._resizing_window = False
        self._last_mouse_pos = None
        self._window_drag_offset = QtCore.QPoint(0, 0)
        self._resize_start_geo = None  # (start_rect, start_pos)
        # Resize grip size (bottom-right corner)
        self._resize_grip = 16

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
        # Handle drag start for window/model or click
        if event.button() == QtCore.Qt.LeftButton:
            pos = event.pos()
            mods = event.modifiers()
            # Check if clicking on resize grip area (bottom-right)
            if (self.width() - pos.x() <= self._resize_grip) and (self.height() - pos.y() <= self._resize_grip):
                self._resizing_window = True
                self._resize_start_geo = (self.window().geometry(), self.mapToGlobal(pos))
                return

            if mods & QtCore.Qt.AltModifier:
                # Alt + Left: drag model in-canvas
                self._dragging_model = True
                self._last_mouse_pos = pos
                return

            # If click is on empty area (no hit), start window drag; else treat as click
            try:
                gpos = self.mapToGlobal(pos)
                hit = False
                try:
                    hit = self.controller.hit_test(gpos.x(), gpos.y())
                except Exception:
                    # if hit_test not reliable, fallback to collider dispatch result
                    hit = self.controller.handle_click(gpos.x(), gpos.y())

                if not hit:
                    # Start dragging window by storing offset from window top-left
                    self._dragging_window = True
                    self._window_drag_offset = gpos - self.window().frameGeometry().topLeft()
                else:
                    # Dispatch click to colliders; if none handled, play random motion
                    handled = self.controller.handle_click(gpos.x(), gpos.y())
                    if not handled:
                        self.controller.start_random_motion()
            except Exception:
                traceback.print_exc()

    def mouseMoveEvent(self, event):
        try:
            pos = event.pos()
            gpos = self.mapToGlobal(pos)
            # Update cursor when near resize grip
            if (self.width() - pos.x() <= self._resize_grip) and (self.height() - pos.y() <= self._resize_grip):
                try:
                    self.setCursor(QtCore.Qt.SizeFDiagCursor)
                except Exception:
                    pass
            else:
                try:
                    self.unsetCursor()
                except Exception:
                    pass
            if self._resizing_window and self._resize_start_geo is not None:
                start_rect, start_gpos = self._resize_start_geo
                delta = gpos - start_gpos
                new_w = max(100, start_rect.width() + delta.x())
                new_h = max(100, start_rect.height() + delta.y())
                self.window().resize(new_w, new_h)
                return

            # Handle model position dragging (Alt + Left)
            if self._dragging_model and self._last_mouse_pos is not None:
                dx = pos.x() - self._last_mouse_pos.x()
                dy = pos.y() - self._last_mouse_pos.y()
                self._last_mouse_pos = pos
                # Translate model by drag delta
                self.controller.translate_model(dx, dy)
                return

            # Handle window dragging when clicking on empty area
            if self._dragging_window:
                new_top_left = gpos - self._window_drag_offset
                self.window().move(new_top_left)
                return

            # Default: pass coordinates to model for look/drag behavior
            self.controller.drag(pos.x(), pos.y())
        except Exception:
            traceback.print_exc()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self._dragging_model = False
            self._dragging_window = False
            self._resizing_window = False
            self._last_mouse_pos = None
            self._resize_start_geo = None

    def wheelEvent(self, event):
        """Handle mouse wheel events for scaling the model. Hold Shift for finer scale."""
        try:
            current_scale = self.controller.get_model_scale()
            delta_steps = event.angleDelta().y() / 120.0
            if delta_steps == 0:
                return
            # finer control with Shift
            step = 0.05 if (event.modifiers() & QtCore.Qt.ShiftModifier) else 0.1
            # Convert steps to multiplicative factor approximately
            new_scale = max(0.1, min(5.0, current_scale * (1.0 + step * delta_steps)))
            self.controller.set_model_scale(new_scale)
        except Exception:
            traceback.print_exc()

    def leaveEvent(self, event):
        # reset cursor when leaving the widget
        try:
            self.unsetCursor()
        except Exception:
            pass

    def mouseMoveEventEvent(self, event):
        # Not used; keeping placeholder for compatibility
        pass