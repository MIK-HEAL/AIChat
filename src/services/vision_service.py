from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

try:  # pragma: no cover - optional dependency
    import mss  # type: ignore
except Exception:  # pragma: no cover
    mss = None  # type: ignore

try:  # pragma: no cover - optional dependency
    import numpy as np  # type: ignore
except Exception:  # pragma: no cover
    np = None  # type: ignore

try:  # pragma: no cover - optional dependency
    from PIL import Image  # type: ignore
except Exception:  # pragma: no cover
    Image = None  # type: ignore

try:  # pragma: no cover - optional dependency
    import pytesseract  # type: ignore
except Exception:  # pragma: no cover
    pytesseract = None  # type: ignore

from src import config

VisionListener = Callable[[Dict[str, Any]], None]


@dataclass
class VisionConfig:
    enabled: bool = False
    capture_interval: float = 10.0
    region: Optional[Dict[str, int]] = None
    ocr_enabled: bool = True
    ocr_language: str = "chi_sim+eng"
    max_history: int = 5

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VisionConfig":
        ocr = data.get("ocr") if isinstance(data, dict) else None
        return cls(
            enabled=bool(data.get("enabled", False)),
            capture_interval=float(data.get("capture_interval", 10.0)),
            region=data.get("region") if isinstance(data.get("region"), dict) else None,
            ocr_enabled=bool((ocr or {}).get("enabled", True)),
            ocr_language=str((ocr or {}).get("language", "chi_sim+eng")),
            max_history=int(data.get("max_history", 5)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "enabled": self.enabled,
            "capture_interval": self.capture_interval,
            "region": self.region,
            "ocr": {
                "enabled": self.ocr_enabled,
                "language": self.ocr_language,
            },
            "max_history": self.max_history,
        }


def load_config() -> VisionConfig:
    path = os.path.join(config.VISION_DIR, "config.json")
    if not os.path.exists(path):
        os.makedirs(config.VISION_DIR, exist_ok=True)
        save_config(VisionConfig())
    try:
        with open(path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
        if isinstance(data, dict):
            return VisionConfig.from_dict(data)
    except Exception:
        pass
    return VisionConfig()


def save_config(cfg: VisionConfig) -> None:
    os.makedirs(config.VISION_DIR, exist_ok=True)
    path = os.path.join(config.VISION_DIR, "config.json")
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(cfg.to_dict(), fp, ensure_ascii=False, indent=2)


@dataclass
class VisionSnapshot:
    timestamp: float
    text: str
    preview_path: Optional[str] = None
    meta: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "timestamp": self.timestamp,
            "text": self.text,
            "meta": self.meta,
        }
        if self.preview_path:
            data["snapshot"] = self.preview_path
        return data


class ScreenVisionService:
    """Capture screen content periodically and broadcast OCR/preview to listeners."""

    def __init__(self) -> None:
        self._listeners: List[VisionListener] = []
        self._lock = threading.RLock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._cfg = load_config()
        self._history: List[VisionSnapshot] = []

    # ------------------------------------------------------------------
    # Listener management
    # ------------------------------------------------------------------
    def register_listener(self, listener: VisionListener) -> None:
        with self._lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def unregister_listener(self, listener: VisionListener) -> None:
        with self._lock:
            try:
                self._listeners.remove(listener)
            except ValueError:
                pass

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(target=self._run_loop, name="vision-loop", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.5)
        self._thread = None

    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def reload_config(self) -> None:
        self._cfg = load_config()

    # ------------------------------------------------------------------
    # Capture loop
    # ------------------------------------------------------------------
    def _run_loop(self) -> None:
        while not self._stop_event.is_set():
            interval = self._cfg.capture_interval
            if interval <= 0:
                interval = 10.0
            if self._cfg.enabled:
                snapshot = self._capture_once()
                if snapshot is not None:
                    self._history.append(snapshot)
                    self._history = self._history[-self._cfg.max_history :]
                    self._emit(snapshot)
            self._stop_event.wait(interval)

    def _capture_once(self) -> Optional[VisionSnapshot]:
        if mss is None:
            return None
        try:
            with mss.mss() as sct:  # type: ignore[attr-defined]
                monitor = self._cfg.region or sct.monitors[1]
                raw = sct.grab(monitor)
                pil_image = self._to_image(raw)
                text = ""
                preview_path = None

                if pil_image is not None:
                    timestamp = time.time()
                    os.makedirs(config.VISION_DIR, exist_ok=True)
                    preview_path = os.path.join(
                        config.VISION_DIR,
                        f"snapshot_{int(timestamp * 1000)}.jpg",
                    )
                    try:
                        pil_image.save(preview_path, format="JPEG", quality=85)
                    except Exception:
                        preview_path = None

                    if self._cfg.ocr_enabled and pytesseract is not None:
                        try:
                            text = pytesseract.image_to_string(pil_image, lang=self._cfg.ocr_language)
                        except Exception:
                            text = ""
                else:
                    timestamp = time.time()

                meta = {
                    "region": monitor,
                    "width": getattr(raw, "width", None),
                    "height": getattr(raw, "height", None),
                }
                return VisionSnapshot(
                    timestamp=timestamp,
                    text=(text or "").strip(),
                    preview_path=preview_path,
                    meta=meta,
                )
        except Exception:
            return None

    def _to_image(self, raw: Any) -> Optional[Any]:
        if Image is None:
            return None
        if np is not None:
            try:
                arr = np.array(raw)
                if arr.ndim == 3 and arr.shape[2] >= 3:
                    rgb = arr[:, :, :3][:, :, ::-1]
                    return Image.fromarray(rgb)
            except Exception:
                pass
        try:
            return Image.frombytes("RGB", raw.size, raw.rgb)  # type: ignore[attr-defined]
        except Exception:
            return None

    # ------------------------------------------------------------------
    # Notification helpers
    # ------------------------------------------------------------------
    def _emit(self, snapshot: VisionSnapshot) -> None:
        payload = {
            "type": "vision",
            "payload": snapshot.to_dict(),
        }
        with self._lock:
            listeners = list(self._listeners)
        for listener in listeners:
            try:
                listener(payload)
            except Exception:
                continue

    # ------------------------------------------------------------------
    # Utilities
    # ------------------------------------------------------------------
    def history(self) -> List[VisionSnapshot]:
        return list(self._history)

    def simulate_detection(self, text: str, meta: Optional[Dict[str, Any]] = None) -> None:
        snapshot = VisionSnapshot(timestamp=time.time(), text=text, meta=meta or {})
        self._emit(snapshot)
