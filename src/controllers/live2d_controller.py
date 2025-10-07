from typing import Optional
from pathlib import Path

from ..live2d.manager import Live2DManager
from ..config import MODEL_PATH


class Live2DController:
    def __init__(self, manager: Optional[Live2DManager] = None):
        self.manager = manager or Live2DManager()
        self.model_loaded = False
        # register default click behaviors when available
        def _play_tap(name: str, x: float, y: float):
            # Map collider to a motion group
            group = 'Tap' if name == 'head' else 'Tap@Body'
            try:
                self.manager.start_random_motion(group)
            except Exception:
                pass

        # delay handler registration until model loaded to avoid early triggers
        self._default_click_handler = _play_tap

    def initialize_gl(self):
        self.manager.initialize()

    def load_model_if_needed(self, path: str | None = None):
        if not self.model_loaded:
            model_path = path or MODEL_PATH
            self.manager.load_model(str(Path(model_path)))
            self.model_loaded = True
            # attach default handlers for common colliders ('head', 'body')
            try:
                self.manager.add_click_handler('head', self._default_click_handler)
                self.manager.add_click_handler('body', self._default_click_handler)
            except Exception:
                pass

    def update_and_draw(self):
        self.manager.update_and_draw()

    def drag(self, x: float, y: float):
        self.manager.drag(x, y)

    def start_random_motion(self, group: str | None = None, priority: int = 3) -> bool:
        return self.manager.start_random_motion(group, priority)

    def resize(self, w: int, h: int):
        self.manager.resize(w, h)

    def dispose(self):
        self.manager.dispose()

    # --- Colliders facade ---
    def register_rect_collider(self, name: str, x: float, y: float, w: float, h: float):
        from ..live2d.collision import RectCollider
        self.manager.register_collider(RectCollider(name=name, x=x, y=y, width=w, height=h))

    def register_circle_collider(self, name: str, cx: float, cy: float, r: float):
        from ..live2d.collision import CircleCollider
        self.manager.register_collider(CircleCollider(name=name, cx=cx, cy=cy, r=r))

    def register_polygon_collider(self, name: str, points):
        from ..live2d.collision import PolygonCollider
        self.manager.register_collider(PolygonCollider(name=name, points=list(points)))

    def handle_click(self, sx: float, sy: float) -> bool:
        # sx, sy are screen coordinates; return True if any collider handled it
        return self.manager.on_click(sx, sy)

    def hit_test(self, sx: float, sy: float) -> bool:
        """Return True if the screen coordinate hits any part of the model."""
        return self.manager.hit_test(sx, sy)

    # --- Transform API ---
    def set_model_position(self, x: float, y: float):
        """Set model position offset."""
        self.manager.set_position(x, y)

    def get_model_position(self) -> tuple[float, float]:
        """Get current model position offset."""
        return self.manager.get_position()

    def set_model_scale(self, scale: float):
        """Set model scale factor."""
        self.manager.set_scale(scale)

    def get_model_scale(self) -> float:
        """Get current model scale factor."""
        return self.manager.get_scale()

    def translate_model(self, dx: float, dy: float):
        """Move model by relative offset."""
        self.manager.translate(dx, dy)

    # --- Expression / parameter API ---
    def apply_parameters(self, parameters: dict[str, float], *, blend: float = 1.0, additive: bool = False) -> bool:
        return self.manager.apply_parameters(parameters, blend=blend, additive=additive)

    # --- Motion API ---
    def start_motion(self, group: str, index: int = 0, priority: int = 3) -> bool:
        return self.manager.start_motion(group, index, priority)

    def start_motion_by_file(self, file_path: str, priority: int = 3) -> bool:
        return self.manager.start_motion_by_file(file_path, priority)

    def find_motion(self, identifier: str) -> Optional[tuple[str, int]]:
        return self.manager.find_motion(identifier)

    def list_motions(self) -> dict[str, list[str]]:
        return self.manager.list_motions()
