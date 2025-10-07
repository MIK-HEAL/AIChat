from __future__ import annotations

import json
import logging
from urllib.parse import urlparse, urlunparse
from typing import Any, Dict, List, Optional, Tuple

from src.services.chat_types import ChatMessage, ChatCommand, ChatResponse

try:  # pragma: no cover - optional dependency
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None  # type: ignore

LOGGER = logging.getLogger(__name__)


class ChatClient:
    """Thin HTTP client for chatting with a configurable LLM endpoint."""

    def __init__(self, settings: Optional[Dict[str, Any]] = None, prompts: Optional[Dict[str, Any]] = None):
        self._settings: Dict[str, Any] = {}
        self._prompts: Dict[str, Any] = {}
        self._host_hint: str = ""
        self.update_config(settings or {}, prompts or {})

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def update_config(self, settings: Dict[str, Any], prompts: Dict[str, Any]) -> None:
        self._settings = dict(settings or {})
        self._prompts = dict(prompts or {})
        self._host_hint = ""

    def send(self, history: List[ChatMessage], user_text: str) -> ChatResponse:
        url = self._resolve_url(self._settings.get("api_url"))
        if not url:
            offline_reply = f"（未配置对话接口，暂时使用离线回复）{user_text}"
            return ChatResponse(text=offline_reply, status="offline")

        payload = self._build_payload(history, user_text)
        headers = self._build_headers()

        if requests is None:
            LOGGER.warning("requests 模块不可用，回退为本地占位回复")
            placeholder = self._placeholder_reply(user_text)
            return ChatResponse(text=placeholder, status="offline")

        try:
            response = requests.post(url, headers=headers, json=payload, timeout=30)
        except Exception as exc:  # pragma: no cover - network dependent
            LOGGER.exception("ChatClient 请求失败: %s", exc)
            friendly_error = f"无法连接到对话服务：{exc}"
            return ChatResponse(text=friendly_error, status="error", error=str(exc))

        if response.status_code >= 400:
            detail = self._extract_error_detail(response)
            LOGGER.error("对话服务返回错误 %s: %s", response.status_code, detail)
            friendly_error = f"对话服务响应异常（{response.status_code}）：{detail}"
            return ChatResponse(text=friendly_error, status="error", error=detail)

        try:
            data = response.json()
        except Exception as exc:  # pragma: no cover
            LOGGER.exception("解析对话服务响应失败: %s", exc)
            friendly_error = f"无法解析对话服务响应：{exc}"
            return ChatResponse(text=friendly_error, status="error", error=str(exc))

        return self._parse_response(data)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _build_payload(self, history: List[ChatMessage], user_text: str) -> Dict[str, Any]:
        messages: List[Dict[str, str]] = []
        system_prompt = (self._prompts.get("system_prompt") or "").strip()
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        for msg in history:
            messages.append({"role": msg.role, "content": msg.content})
        messages.append({"role": "user", "content": user_text})

        payload: Dict[str, Any] = {
            "messages": messages,
        }
        model = (self._settings.get("model") or "").strip()
        model = self._normalize_model(model)
        if model:
            payload["model"] = model
        stream = self._settings.get("stream")
        if isinstance(stream, bool):
            payload["stream"] = stream
        if "temperature" in self._settings:
            try:
                payload["temperature"] = float(self._settings["temperature"])
            except (TypeError, ValueError):
                pass
        return payload

    def _build_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        api_key = (self._settings.get("api_key") or "").strip()
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        return headers

    def _resolve_url(self, url_value: Optional[str]) -> str:
        url = (url_value or "").strip()
        if not url:
            return ""
        parsed = urlparse(url)
        if not parsed.scheme:
            # allow users to omit scheme, default to https
            parsed = urlparse(f"https://{url}")

        path = parsed.path or ""
        netloc = parsed.netloc.lower()
        self._host_hint = netloc

        # DeepSeek host helper
        if netloc.endswith("deepseek.com"):
            if not path or path == "/":
                path = "/chat/completions"
        # OpenAI compatible helper
        elif "openai" in netloc and (not path or path == "/"):
            path = "/v1/chat/completions"

        if not path.startswith("/"):
            path = f"/{path}"

        normalized = parsed._replace(path=path or "/")
        return urlunparse(normalized)

    def _normalize_model(self, model: str) -> str:
        host = (self._host_hint or "").lower()
        normalized = model.strip()
        if host.endswith("deepseek.com"):
            if not normalized:
                normalized = "deepseek-chat"
            elif not normalized.startswith("deepseek"):
                LOGGER.warning("检测到 DeepSeek 接口，模型名 %s 不兼容，已自动改为 deepseek-chat", normalized)
                normalized = "deepseek-chat"
        return normalized

    def _extract_error_detail(self, response: Any) -> str:
        try:
            data = response.json()
        except Exception:
            return response.text.strip() or response.reason

        if isinstance(data, dict):
            if isinstance(data.get("error"), dict):
                return data["error"].get("message") or str(data["error"])
            if data.get("message"):
                return str(data["message"])
            if data.get("detail"):
                return str(data["detail"])
        return str(data)

    def _parse_response(self, data: Any) -> ChatResponse:
        if isinstance(data, str):
            data = data.strip()
            if data.startswith("{"):
                try:
                    data = json.loads(data)
                except json.JSONDecodeError:
                    return ChatResponse(text=data)
            else:
                return ChatResponse(text=data)

        text = ""
        commands: List[ChatCommand] = []
        raw_message: Optional[Dict[str, Any]] = None

        if isinstance(data, dict):
            # OpenAI style
            choices = data.get("choices")
            if isinstance(choices, list) and choices:
                message_obj = choices[0].get("message") if isinstance(choices[0], dict) else None
                if isinstance(message_obj, dict):
                    raw_message = message_obj
                    text = (message_obj.get("content") or "").strip()
                    commands = self._extract_commands(message_obj)

            # Direct reply style
            if not text:
                text = (data.get("reply") or data.get("content") or data.get("message") or "").strip()

            if not commands and isinstance(data.get("commands"), list):
                commands = self._convert_command_list(data.get("commands"))

            # Some providers wrap JSON in content field
            if text and text.startswith("{"):
                try:
                    parsed_text = json.loads(text)
                except json.JSONDecodeError:
                    parsed_text = None
                if isinstance(parsed_text, dict):
                    text = (parsed_text.get("reply") or parsed_text.get("content") or "").strip()
                    if not text and "text" in parsed_text:
                        text = str(parsed_text["text"]).strip()
                    if not commands and isinstance(parsed_text.get("commands"), list):
                        commands = self._convert_command_list(parsed_text.get("commands"))
        elif isinstance(data, list) and data:
            text = str(data[0])

        clean_text, inline_commands = self._extract_inline_commands_from_text(text)
        if inline_commands:
            commands.extend(inline_commands)
            text = clean_text

        if not text.strip():
            text = "（已处理指令）" if inline_commands else "（对话服务未返回内容）"
        else:
            text = text.strip()

        return ChatResponse(text=text, commands=commands, raw=raw_message or data)

    def _extract_commands(self, message_obj: Dict[str, Any]) -> List[ChatCommand]:
        # OpenAI tool calls can appear under function_call or tool_calls
        commands: List[ChatCommand] = []
        tool_calls = message_obj.get("tool_calls")
        if isinstance(tool_calls, list):
            for call in tool_calls:
                if not isinstance(call, dict):
                    continue
                function = call.get("function")
                if not isinstance(function, dict):
                    continue
                name = function.get("name")
                arguments = function.get("arguments")
                payload: Dict[str, Any]
                if isinstance(arguments, str):
                    try:
                        payload = json.loads(arguments)
                    except json.JSONDecodeError:
                        payload = {"raw": arguments}
                elif isinstance(arguments, dict):
                    payload = arguments
                else:
                    payload = {}
                if isinstance(name, str) and name:
                    commands.append(ChatCommand(type=name, payload=payload))
        return commands

    def _convert_command_list(self, source: Any) -> List[ChatCommand]:
        commands: List[ChatCommand] = []
        if not isinstance(source, list):
            return commands
        for item in source:
            if isinstance(item, dict) and item.get("type"):
                payload = {k: v for k, v in item.items() if k != "type"}
                commands.append(ChatCommand(type=str(item["type"]), payload=payload))
        return commands

    def _placeholder_reply(self, user_text: str) -> str:
        return f"（离线占位回复）我听到了你说：{user_text}"

    # ------------------------------------------------------------------
    # Inline command parsing helpers
    # ------------------------------------------------------------------
    def _extract_inline_commands_from_text(self, text: str) -> Tuple[str, List[ChatCommand]]:
        if not text:
            return text, []
        commands: List[ChatCommand] = []
        decoder = json.JSONDecoder()
        idx = 0
        keep_segments: List[str] = []
        last_end = 0
        length = len(text)

        while idx < length:
            char = text[idx]
            if char not in "{[":
                idx += 1
                continue
            try:
                obj, consumed = decoder.raw_decode(text[idx:])
            except ValueError:
                idx += 1
                continue
            absolute_end = idx + consumed
            candidate_commands = self._objects_to_commands(obj)
            if candidate_commands:
                keep_segments.append(text[last_end:idx])
                commands.extend(candidate_commands)
                last_end = absolute_end
            idx = absolute_end

        keep_segments.append(text[last_end:])
        cleaned = "".join(keep_segments)
        return cleaned.strip(), commands

    def _objects_to_commands(self, obj: Any) -> List[ChatCommand]:
        commands: List[ChatCommand] = []
        if isinstance(obj, list):
            for item in obj:
                commands.extend(self._objects_to_commands(item))
        elif isinstance(obj, dict):
            if "$schema" in obj:
                commands.extend(self._objects_to_commands(obj["$schema"]))
            cmd_type = obj.get("type")
            if isinstance(cmd_type, str) and cmd_type:
                payload = obj.get("payload")
                if not isinstance(payload, dict):
                    payload = {k: v for k, v in obj.items() if k not in {"type", "payload"}}
                commands.append(ChatCommand(type=cmd_type, payload=dict(payload)))
            elif "expression" in obj and isinstance(obj["expression"], str):
                commands.append(ChatCommand(type="expression", payload={"name": obj["expression"]}))
            elif "name" in obj and isinstance(obj["name"], str):
                commands.append(ChatCommand(type="expression", payload={"name": obj["name"]}))
        return commands
