from __future__ import annotations

import time
import threading
from typing import Any, Callable, Dict, List, Optional, TYPE_CHECKING

from src.services.chat_client import ChatClient
from src.services.chat_types import ChatCommand, ChatMessage, ChatResponse
from src.services.expression_manager import ExpressionManager
from src.utils import storage

if TYPE_CHECKING:  # pragma: no cover
    from src.controllers.live2d_controller import Live2DController
    from src.services.vision_service import ScreenVisionService

CommandHandler = Callable[[ChatCommand], None]


class ChatManager:
    """Maintain conversation history and bridge AI commands to the Live2D controller."""

    def __init__(self, controller: Optional["Live2DController"] = None):
        self._lock = threading.RLock()
        self._history: List[ChatMessage] = []
        self._controller: Optional["Live2DController"] = controller
        self._command_handlers: List[CommandHandler] = []
        self._vision_service: Optional["ScreenVisionService"] = None
        self._vision_lock = threading.RLock()
        self._pending_commands: List[ChatCommand] = []
        self._last_vision_timestamp: float = 0.0

        self._user_settings = storage.load_user_settings()
        self._ai_prompts = storage.load_ai_prompts()
        self._client = ChatClient(self._user_settings, self._ai_prompts)
        self._expression_manager = ExpressionManager(controller)

        # default handler to forward Live2D commands
        self.register_command_handler(self._handle_live2d_command)

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------
    def reload_config(self) -> None:
        with self._lock:
            self._user_settings = storage.load_user_settings()
            self._ai_prompts = storage.load_ai_prompts()
            self._client.update_config(self._user_settings, self._ai_prompts)
            self._expression_manager.reload()
            if self._vision_service is not None:
                self._vision_service.reload_config()

    def set_controller(self, controller: Optional["Live2DController"]) -> None:
        with self._lock:
            self._controller = controller
            self._expression_manager.set_controller(controller)

    # ------------------------------------------------------------------
    # Conversation
    # ------------------------------------------------------------------
    def reset_history(self) -> None:
        with self._lock:
            self._history.clear()

    def get_history(self) -> List[ChatMessage]:
        with self._lock:
            return list(self._history)

    def send_user_message(self, text: str) -> ChatResponse:
        with self._lock:
            history_snapshot = list(self._history)
        response = self._client.send(history_snapshot, text)
        with self._lock:
            self._history.append(ChatMessage(role="user", content=text))
            self._history.append(ChatMessage(role="assistant", content=response.text))
        return response

    def apply_commands(self, commands: List[ChatCommand]) -> None:
        if not commands:
            return
        handlers = list(self._command_handlers)
        for command in commands:
            for handler in handlers:
                try:
                    handler(command)
                except Exception:  # pragma: no cover - safe guard
                    continue

    # ------------------------------------------------------------------
    # Command handlers
    # ------------------------------------------------------------------
    def register_command_handler(self, handler: CommandHandler) -> None:
        if handler not in self._command_handlers:
            self._command_handlers.append(handler)

    def unregister_command_handler(self, handler: CommandHandler) -> None:
        try:
            self._command_handlers.remove(handler)
        except ValueError:
            pass

    def _handle_live2d_command(self, command: ChatCommand) -> None:
        controller = self._controller
        if controller is None:
            return
        cmd_type = command.type.lower()
        payload = command.payload or {}

        if cmd_type in {"motion", "start_motion", "play_motion"}:
            self._handle_motion_command(controller, payload)
        elif cmd_type in {"scale", "set_scale"}:
            value = payload.get("value") or payload.get("scale")
            try:
                if value is not None:
                    controller.set_model_scale(float(value))
            except Exception:
                pass
        elif cmd_type in {"move", "translate"}:
            dx = payload.get("dx", 0)
            dy = payload.get("dy", 0)
            try:
                controller.translate_model(float(dx), float(dy))
            except Exception:
                pass
        elif cmd_type in {"position", "set_position"}:
            x = payload.get("x")
            y = payload.get("y")
            try:
                if x is not None and y is not None:
                    controller.set_model_position(float(x), float(y))
            except Exception:
                pass
        elif cmd_type in {"look", "drag"}:
            # simulate a drag to make模型 LookAt
            x = payload.get("x")
            y = payload.get("y")
            try:
                if x is not None and y is not None:
                    controller.drag(float(x), float(y))
            except Exception:
                pass
        elif cmd_type in {"expression", "set_expression", "face"}:
            name = payload.get("name") or payload.get("value") or payload.get("expression")
            blend = payload.get("blend") or payload.get("weight") or 1.0
            additive = bool(payload.get("additive", False))
            try:
                blend_value = float(blend)
            except (TypeError, ValueError):
                blend_value = 1.0
            if isinstance(name, str) and name:
                applied = self._expression_manager.apply_expression(name, blend=blend_value, additive=additive)
                if not applied and isinstance(payload.get("parameters"), dict):
                    parameters = {
                        key: float(value)
                        for key, value in payload["parameters"].items()
                        if isinstance(value, (int, float))
                    }
                    if parameters:
                        self._expression_manager.apply_parameters(parameters, blend=blend_value, additive=additive)
            elif isinstance(payload.get("parameters"), dict):
                parameters = {
                    key: float(value)
                    for key, value in payload["parameters"].items()
                    if isinstance(value, (int, float))
                }
                if parameters:
                    self._expression_manager.apply_parameters(parameters, blend=blend_value, additive=additive)
        # Future command types (expression, physics, etc.) can be added here
    def _handle_motion_command(self, controller: "Live2DController", payload: Dict[str, Any]) -> None:
        group = payload.get("group")
        index = payload.get("index")
        file_name = payload.get("file") or payload.get("path") or payload.get("motionFile")
        identifier = payload.get("motion") or payload.get("name") or payload.get("value")
        priority = payload.get("priority")
        try:
            priority_value = int(priority) if priority is not None else 3
        except (TypeError, ValueError):
            priority_value = 3

        if isinstance(index, str):
            try:
                index = int(index)
            except ValueError:
                index = None
        if isinstance(index, (float, int)):
            index_value: Optional[int] = int(index)
        else:
            index_value = None

        # Try direct group + index
        if isinstance(group, str) and group:
            if index_value is not None:
                if controller.start_motion(group, index_value, priority_value):
                    return
            if isinstance(file_name, str) and controller.start_motion_by_file(file_name, priority_value):
                return
            if isinstance(identifier, str):
                info = controller.find_motion(identifier)
                if info and info[0] == group:
                    if controller.start_motion(info[0], info[1], priority_value):
                        return
            # fallback to random motion in the group
            controller.start_random_motion(group, priority_value)
            return

        # Try by file or identifier without group
        candidate = file_name or identifier
        if isinstance(candidate, str):
            info = controller.find_motion(candidate)
            if info and controller.start_motion(info[0], info[1], priority_value):
                return

        # Last fallback: any random motion
        controller.start_random_motion(None, priority_value)

    def attach_vision_service(self, service: Optional["ScreenVisionService"]) -> None:
        with self._lock:
            if self._vision_service is service:
                return
            if self._vision_service is not None:
                self._vision_service.unregister_listener(self._on_vision_event)
            self._vision_service = service
            if service is not None:
                service.register_listener(self._on_vision_event)

    def _on_vision_event(self, payload: dict) -> None:
        if not isinstance(payload, dict):
            return
        if payload.get("type") != "vision":
            return
        data = payload.get("payload")
        if not isinstance(data, dict):
            return

        timestamp = float(data.get("timestamp") or 0.0)
        text = str(data.get("text") or "").strip()
        snapshot_path = data.get("snapshot") if isinstance(data.get("snapshot"), str) else None
        if not text and not snapshot_path:
            return

        with self._vision_lock:
            if timestamp and timestamp <= self._last_vision_timestamp:
                return
            self._last_vision_timestamp = timestamp or time.time()

        summary = self._format_vision_prompt(text, data, snapshot_path)
        if not summary:
            return

        with self._lock:
            history_snapshot = list(self._history)

        response = self._client.send(history_snapshot, summary)

        with self._lock:
            self._history.append(ChatMessage(role="system", content=summary))
            if response.text:
                self._history.append(ChatMessage(role="assistant", content=response.text))
            if response.status == "ok" and response.commands:
                self._pending_commands.extend(response.commands)

    def _format_vision_prompt(self, text: str, payload: Dict[str, Any], snapshot_path: Optional[str]) -> str:
        lines = ["[视觉捕获]"]
        if text:
            lines.append(text)
        meta = payload.get("meta")
        if not isinstance(meta, dict):
            meta = {}
        width = meta.get("width")
        height = meta.get("height")
        if width and height:
            lines.append(f"区域大小：{width}x{height}")
        if snapshot_path:
            lines.append(f"截图路径：{snapshot_path}")
        return "\n".join(line for line in lines if line).strip()

    def drain_pending_commands(self) -> List[ChatCommand]:
        with self._lock:
            commands = list(self._pending_commands)
            self._pending_commands.clear()
        return commands

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------
    @property
    def user_settings(self) -> dict:
        return dict(self._user_settings)

    @property
    def ai_prompts(self) -> dict:
        return dict(self._ai_prompts)

    def get_greeting(self) -> str:
        greeting = self._ai_prompts.get("greeting")
        return str(greeting) if greeting else ""

    def list_expressions(self) -> List[str]:
        with self._lock:
            return list(self._expression_manager.list_expressions())

    def list_motions(self) -> Dict[str, List[str]]:
        with self._lock:
            controller = self._controller
            if controller is None:
                return {}
            return controller.list_motions()
