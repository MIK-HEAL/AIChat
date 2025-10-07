"""Backward-compatible re-exports for the vision service implementation."""

from src.services.vision_service import (  # noqa: F401
    ScreenVisionService,
    VisionConfig,
    VisionSnapshot,
    load_config,
    save_config,
)

__all__ = [
    "ScreenVisionService",
    "VisionConfig",
    "VisionSnapshot",
    "load_config",
    "save_config",
]
