from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Iterable, List, Tuple


class Collider(Protocol):
    name: str
    enabled: bool
    def contains(self, x: float, y: float, ctx: object | None = None) -> bool: ...


@dataclass
class BaseCollider:
    name: str
    enabled: bool = True

    def contains(self, x: float, y: float, ctx: object | None = None) -> bool:
        raise NotImplementedError


@dataclass
class RectCollider(BaseCollider):
    # axis-aligned rectangle in screen coordinates
    x: float = 0
    y: float = 0
    width: float = 0
    height: float = 0

    def contains(self, x: float, y: float, ctx: object | None = None) -> bool:
        if not self.enabled:
            return False
        return (self.x <= x <= self.x + self.width) and (self.y <= y <= self.y + self.height)


@dataclass
class CircleCollider(BaseCollider):
    cx: float = 0
    cy: float = 0
    r: float = 0

    def contains(self, x: float, y: float, ctx: object | None = None) -> bool:
        if not self.enabled:
            return False
        dx, dy = x - self.cx, y - self.cy
        return (dx * dx + dy * dy) <= (self.r * self.r)


@dataclass
class PolygonCollider(BaseCollider):
    # simple polygon in screen coordinates
    points: List[Tuple[float, float]] = None

    def contains(self, x: float, y: float, ctx: object | None = None) -> bool:
        if not self.enabled or not self.points or len(self.points) < 3:
            return False
        # ray casting algorithm
        cnt = 0
        n = len(self.points)
        px, py = x, y
        for i in range(n):
            x1, y1 = self.points[i]
            x2, y2 = self.points[(i + 1) % n]
            if ((y1 > py) != (y2 > py)):
                xinters = (px - x1) * (y2 - y1)
                if (y2 - y1) != 0:
                    xinters = x1 + (px - x1) * (py - y1) / (y2 - y1)
                if px < xinters:
                    cnt += 1
        return (cnt % 2) == 1


class HitAreaCollider(BaseCollider):
    """Collider based on Live2D model hit areas, using area name like 'Head' or 'Body'.

    ctx is expected to be a model object exposing HitTest(area_name, x, y).
    """

    def __init__(self, name: str, area_name: str, enabled: bool = True):
        super().__init__(name=name, enabled=enabled)
        self.area_name = area_name

    def contains(self, x: float, y: float, ctx: object | None = None) -> bool:
        if not self.enabled or ctx is None:
            return False
        try:
            if hasattr(ctx, 'HitTest'):
                return bool(ctx.HitTest(self.area_name, x, y))
        except Exception:
            return False
        return False
