import json
import os
import traceback
from typing import Optional, List, Tuple, Callable, Dict

import live2d.v3 as live2d
from .collision import Collider, HitAreaCollider, RectCollider, CircleCollider, PolygonCollider


class Live2DManager:
    """Encapsulate live2d calls so UI/controller code doesn't import live2d directly."""

    def __init__(self):
        self.model = None
        self.initialized = False
        self._colliders: List[Collider] = []
        self._click_handlers: List[Tuple[str, Callable[[str, float, float], None]]] = []
        # Model transform parameters
        self.model_x = 0.0  # X offset
        self.model_y = 0.0  # Y offset  
        self.model_scale = 1.0  # Scale factor
        # cache for parameter operations
        self._parameter_method_cache: Dict[str, Callable] = {}
        self._motion_groups: Dict[str, List[str]] = {}
        self._motion_lookup: Dict[str, Tuple[str, int]] = {}

    def initialize(self):
        if self.initialized:
            return
        if hasattr(live2d, 'init'):
            live2d.init()
        if hasattr(live2d, 'glewInit'):
            try:
                live2d.glewInit()
            except Exception:
                traceback.print_exc()
        if hasattr(live2d, 'glInit'):
            live2d.glInit()
        self.initialized = True

    def load_model(self, model_json_path: str):
        if not self.initialized:
            raise RuntimeError('Live2D not initialized')
        if not os.path.exists(model_json_path):
            raise FileNotFoundError(model_json_path)
        self.model = live2d.LAppModel()
        self.model.LoadModelJson(model_json_path)
        self._parameter_method_cache.clear()
        self._load_motion_metadata(model_json_path)
        # Default colliders for convenience if model exposes these areas
        # Users can override via register_collider
        self._colliders.clear()
        for area in ('Head', 'Body'):
            self._colliders.append(HitAreaCollider(name=area.lower(), area_name=area))

    def update_and_draw(self):
        if self.model is None:
            return
        # Apply transform before drawing
        if hasattr(self.model, 'SetMatrix'):
            # Create transformation matrix with translation and scale
            try:
                # Most Live2D implementations use a 4x4 matrix or expose SetPosition/SetScale
                if hasattr(self.model, 'SetPosition'):
                    self.model.SetPosition(self.model_x, self.model_y)
                if hasattr(self.model, 'SetScale'):
                    self.model.SetScale(self.model_scale, self.model_scale)
            except Exception:
                traceback.print_exc()
        
        self.model.Update()
        self.model.Draw()

    def drag(self, x: float, y: float):
        """Pass mouse drag coordinates (window relative) to the live2d model."""
        if self.model is None:
            return
        try:
            # LAppModel.Drag expects window relative coordinates
            if hasattr(self.model, 'Drag'):
                self.model.Drag(x, y)
        except Exception:
            traceback.print_exc()

    def start_random_motion(self, group: str | None = None, priority: int = 3) -> bool:
        if self.model is None:
            return False
        try:
            # Prefer StartRandomMotion API if available
            if hasattr(self.model, 'StartRandomMotion'):
                if group is None:
                    self.model.StartRandomMotion(priority=priority)
                else:
                    self.model.StartRandomMotion(group, priority)
                return True
            elif hasattr(self.model, 'StartMotion') and isinstance(group, str):
                # fallback: start first motion in the specified group
                self.model.StartMotion(group, 0, priority)
                return True
        except Exception:
            traceback.print_exc()
        return False

    def hit_test(self, x: float, y: float) -> bool:
        """Return True if the screen coordinate (x,y) hits the model's drawable/part."""
        if self.model is None:
            return False
        try:
            # Prefer HitTest / IsAreaHit API if available
            if hasattr(self.model, 'HitTest'):
                # HitTest in v3 expects (hitAreaName, x, y) but there is also HitPart which returns list
                # We'll use HitPart to determine if any part is under the point
                if hasattr(self.model, 'HitPart'):
                    parts = self.model.HitPart(x, y)
                    return bool(parts)
                # fallback to HitTest with a known area name if available
                return False
            elif hasattr(self.model, 'IsAreaHit'):
                # try default HitArea name 'Head' or similar
                return self.model.IsAreaHit('Head', x, y)
        except Exception:
            traceback.print_exc()
        return False

    # --- Colliders API ---
    def register_collider(self, collider: Collider):
        self._colliders.append(collider)

    def clear_colliders(self):
        self._colliders.clear()

    def query_colliders(self, x: float, y: float) -> List[str]:
        names: List[str] = []
        ctx = self.model
        for c in self._colliders:
            try:
                if c.contains(x, y, ctx):
                    names.append(c.name)
            except Exception:
                continue
        return names

    def on_click(self, x: float, y: float) -> bool:
        """Dispatch click to registered handlers based on collider hits.

        Handlers are (collider_name, callback) and will be invoked when that collider matches.
        """
        names = self.query_colliders(x, y)
        if not names:
            return False
        for cname, cb in list(self._click_handlers):
            if cname in names:
                try:
                    cb(cname, x, y)
                except Exception:
                    traceback.print_exc()
        return True

    def add_click_handler(self, collider_name: str, callback: Callable[[str, float, float], None]):
        self._click_handlers.append((collider_name, callback))

    def remove_click_handler(self, collider_name: str, callback: Callable[[str, float, float], None]):
        try:
            self._click_handlers.remove((collider_name, callback))
        except ValueError:
            pass

    # --- Transform API ---
    def set_position(self, x: float, y: float):
        """Set model position offset."""
        self.model_x = x
        self.model_y = y

    def get_position(self) -> Tuple[float, float]:
        """Get current model position offset."""
        return self.model_x, self.model_y

    def set_scale(self, scale: float):
        """Set model scale factor."""
        self.model_scale = max(0.1, min(5.0, scale))  # Clamp scale between 0.1 and 5.0

    def get_scale(self) -> float:
        """Get current model scale factor."""
        return self.model_scale

    def translate(self, dx: float, dy: float):
        """Move model by relative offset."""
        self.model_x += dx
        self.model_y += dy

    def resize(self, w: int, h: int):
        if self.model is None:
            return
        try:
            self.model.Resize(w, h)
        except Exception:
            traceback.print_exc()

    def dispose(self):
        try:
            if hasattr(live2d, 'glRelease'):
                live2d.glRelease()
            if hasattr(live2d, 'dispose'):
                live2d.dispose()
        except Exception:
            traceback.print_exc()
        self.model = None
        self.initialized = False
        self._parameter_method_cache.clear()
        self._motion_groups.clear()
        self._motion_lookup.clear()

    # --- Expression / parameter API ---
    def apply_parameters(self, parameters: Dict[str, float], blend: float = 1.0, additive: bool = False) -> bool:
        if self.model is None:
            return False
        applied = False
        for param_id, value in parameters.items():
            if not isinstance(param_id, str):
                continue
            try:
                numeric_value = float(value)
            except (TypeError, ValueError):
                continue
            success = False
            if additive:
                success = self._add_parameter_value(param_id, numeric_value * blend)
                if not success:
                    # fall back to absolute set based on current value
                    base = self._get_parameter_value(param_id)
                    success = self._set_parameter_value(param_id, base + numeric_value * blend)
            else:
                success = self._set_parameter_value(param_id, numeric_value, blend)
            applied = applied or success
        return applied

    # ------------------------------------------------------------------
    # Internal helpers for parameter operations
    # ------------------------------------------------------------------
    def _get_cached_method(self, name: str) -> Optional[Callable]:
        if self.model is None:
            return None
        if name in self._parameter_method_cache:
            return self._parameter_method_cache[name]
        method = getattr(self.model, name, None)
        if callable(method):
            self._parameter_method_cache[name] = method
            return method
        return None

    def _try_call(self, method: Callable, *args) -> bool:
        try:
            method(*args)
            return True
        except TypeError:
            return False
        except Exception:
            traceback.print_exc()
            return True

    def _set_parameter_value(self, param_id: str, value: float, blend: float = 1.0) -> bool:
        method_order = [
            'SetParameterValue',
            'SetParamFloat',
            'SetParamValue',
            'SetParam',
        ]
        for name in method_order:
            method = self._get_cached_method(name)
            if method is None:
                continue
            if self._try_call(method, param_id, value, blend):
                return True
            if self._try_call(method, param_id, value):
                return True
        # Some implementations expose UpdateParameter directly via dictionary access
        setter = self._get_cached_method('UpdateParameter')
        if setter is not None:
            return self._try_call(setter, param_id, value)
        return False

    def _add_parameter_value(self, param_id: str, delta: float) -> bool:
        method = self._get_cached_method('AddParameterValue')
        if method and self._try_call(method, param_id, delta):
            return True
        return False

    def _get_parameter_value(self, param_id: str) -> float:
        getter_order = [
            'GetParameterValue',
            'GetParamFloat',
            'GetParamValue',
            'GetParam',
        ]
        for name in getter_order:
            method = self._get_cached_method(name)
            if method is None:
                continue
            try:
                value = method(param_id)
                return float(value)
            except TypeError:
                continue
            except Exception:
                traceback.print_exc()
                return 0.0
        return 0.0

    # --- Motion metadata & control ---
    def _load_motion_metadata(self, model_json_path: str) -> None:
        self._motion_groups.clear()
        self._motion_lookup.clear()
        try:
            with open(model_json_path, 'r', encoding='utf-8') as fp:
                data = json.load(fp)
        except Exception:
            traceback.print_exc()
            return

        motions = data.get('FileReferences', {}).get('Motions', {})
        if not isinstance(motions, dict):
            return

        for group, entries in motions.items():
            if not isinstance(entries, list):
                continue
            names: List[str] = []
            for index, entry in enumerate(entries):
                if not isinstance(entry, dict):
                    continue
                file_path = entry.get('File')
                if not isinstance(file_path, str):
                    continue
                names.append(file_path)
                key_full = file_path
                key_base = os.path.basename(file_path)
                if key_full not in self._motion_lookup:
                    self._motion_lookup[key_full] = (group, index)
                if key_base and key_base not in self._motion_lookup:
                    self._motion_lookup[key_base] = (group, index)
            if names:
                self._motion_groups[group] = names

    def start_motion(self, group: str, index: int = 0, priority: int = 3) -> bool:
        if self.model is None:
            return False
        try:
            motion_index = max(0, int(index))
        except (TypeError, ValueError):
            motion_index = 0
        try:
            if hasattr(self.model, 'StartMotion'):
                self.model.StartMotion(group, motion_index, priority)
                return True
            if hasattr(self.model, 'StartMotionByName'):
                # Some bindings expose StartMotionByName(group, name)
                group_motions = self._motion_groups.get(group)
                if group_motions and 0 <= motion_index < len(group_motions):
                    self.model.StartMotionByName(group, group_motions[motion_index])
                    return True
        except Exception:
            traceback.print_exc()
        # fallback
        return self.start_random_motion(group, priority)

    def start_motion_by_file(self, file_path: str, priority: int = 3) -> bool:
        if not isinstance(file_path, str):
            return False
        info = self._motion_lookup.get(file_path)
        if not info:
            return False
        group, index = info
        return self.start_motion(group, index, priority)

    def find_motion(self, identifier: str) -> Optional[Tuple[str, int]]:
        if not isinstance(identifier, str):
            return None
        return self._motion_lookup.get(identifier)

    def list_motions(self) -> Dict[str, List[str]]:
        return {group: list(files) for group, files in self._motion_groups.items()}
