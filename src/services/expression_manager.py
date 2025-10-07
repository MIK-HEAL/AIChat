from __future__ import annotations

from typing import Dict, Iterable, Optional, TYPE_CHECKING

from src.utils import storage

if TYPE_CHECKING:  # pragma: no cover - type hints only
    from src.controllers.live2d_controller import Live2DController


def _extract_param_map(definition: object) -> Dict[str, float]:
    """Normalize an expression definition into parameter-value mapping."""
    if isinstance(definition, dict):
        if "parameters" in definition and isinstance(definition["parameters"], dict):
            return {
                key: float(value)
                for key, value in definition["parameters"].items()
                if isinstance(value, (int, float))
            }
        # allow simplified form {"Param": 0.5, "description": "..."}
        return {
            key: float(value)
            for key, value in definition.items()
            if isinstance(value, (int, float))
        }
    return {}


class ExpressionManager:
    """Load and apply expression presets to the Live2D controller."""

    def __init__(self, controller: Optional["Live2DController"] = None):
        self._controller: Optional["Live2DController"] = controller
        self._definitions: Dict[str, object] = {}
        self.reload()

    # ------------------------------------------------------------------
    # Lifecycle & configuration
    # ------------------------------------------------------------------
    def reload(self) -> None:
        self._definitions = storage.load_expressions()

    def set_controller(self, controller: Optional["Live2DController"]) -> None:
        self._controller = controller

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------
    def list_expressions(self) -> Iterable[str]:
        return tuple(self._definitions.keys())

    def get_expression(self, name: str) -> Optional[object]:
        return self._definitions.get(name)

    # ------------------------------------------------------------------
    # Apply helpers
    # ------------------------------------------------------------------
    def apply_expression(self, name: str, *, blend: float = 1.0, additive: bool = False) -> bool:
        if not name:
            return False
        if name not in self._definitions:
            return False
        parameters = _extract_param_map(self._definitions[name])
        if not parameters:
            return False
        return self.apply_parameters(parameters, blend=blend, additive=additive)

    def apply_parameters(self, parameters: Dict[str, float], *, blend: float = 1.0, additive: bool = False) -> bool:
        controller = self._controller
        if controller is None:
            return False
        return controller.apply_parameters(parameters, blend=blend, additive=additive)

    def apply_snapshot(self, snapshot: Dict[str, float], *, blend: float = 1.0) -> bool:
        return self.apply_parameters(snapshot, blend=blend, additive=False)
