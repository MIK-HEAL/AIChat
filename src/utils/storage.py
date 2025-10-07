import json
import os
from typing import Any, Dict

from src import config

DEFAULT_USER_SETTINGS: Dict[str, Any] = {
    "display_name": "默认用户",
    "api_url": "https://api.example.com/v1/chat",
    "api_key": "",
    "model": "gpt-4o-mini",
}

DEFAULT_AI_PROMPTS: Dict[str, Any] = {
    "system_prompt": "你是一个活泼可爱的桌宠助手，善于陪伴用户并提供有趣的互动。",
    "greeting": "嗨～我是桌宠，随时准备和你聊天！",
}

DEFAULT_EXPRESSIONS: Dict[str, Any] = {
    "neutral": {
        "description": "默认表情，眼睛张开，嘴部自然。",
        "parameters": {
            "ParamEyeLOpen": 1.0,
            "ParamEyeROpen": 1.0,
            "ParamEyeLSmile": 0.0,
            "ParamEyeRSmile": 0.0,
            "ParamCheek": 0.0,
            "ParamMouthForm": 0.0,
            "ParamMouthOpenY": 0.2
        }
    },
    "happy": {
        "description": "微笑表情，眼睛弯成弧形，嘴角上扬。",
        "parameters": {
            "ParamEyeLOpen": 0.9,
            "ParamEyeROpen": 0.9,
            "ParamEyeLSmile": 1.0,
            "ParamEyeRSmile": 1.0,
            "ParamCheek": 0.65,
            "ParamMouthForm": 0.7,
            "ParamMouthOpenY": 0.4
        }
    },
    "sad": {
        "description": "略带忧伤，眼睛半闭，嘴角下压。",
        "parameters": {
            "ParamEyeLOpen": 0.35,
            "ParamEyeROpen": 0.35,
            "ParamEyeLSmile": -0.4,
            "ParamEyeRSmile": -0.4,
            "ParamCheek": -0.2,
            "ParamMouthForm": -0.5,
            "ParamMouthOpenY": 0.15
        }
    },
    "angry": {
        "description": "生气表情，眉毛下压，嘴角收紧。",
        "parameters": {
            "ParamEyeLOpen": 0.6,
            "ParamEyeROpen": 0.6,
            "ParamEyeLSmile": -0.6,
            "ParamEyeRSmile": -0.6,
            "ParamBrowLForm": -0.7,
            "ParamBrowRForm": -0.7,
            "ParamCheek": 0.2,
            "ParamMouthForm": -0.3,
            "ParamMouthOpenY": 0.25
        }
    },
    "excited": {
        "description": "惊喜/兴奋，眼睛睁大，嘴部张开。",
        "parameters": {
            "ParamEyeLOpen": 1.0,
            "ParamEyeROpen": 1.0,
            "ParamEyeLSmile": 0.5,
            "ParamEyeRSmile": 0.5,
            "ParamCheek": 0.5,
            "ParamMouthForm": 0.9,
            "ParamMouthOpenY": 0.9
        }
    }
}


def _ensure_file(path: str, defaults: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(defaults, fp, ensure_ascii=False, indent=2)


def _load(path: str, defaults: Dict[str, Any]) -> Dict[str, Any]:
    _ensure_file(path, defaults)
    try:
        with open(path, "r", encoding="utf-8") as fp:
            data = json.load(fp)
            if isinstance(data, dict):
                return {**defaults, **data}
    except FileNotFoundError:
        pass
    except json.JSONDecodeError:
        pass
    return defaults.copy()


def _save(path: str, data: Dict[str, Any], defaults: Dict[str, Any]) -> Dict[str, Any]:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    merged = {**defaults, **data}
    with open(path, "w", encoding="utf-8") as fp:
        json.dump(merged, fp, ensure_ascii=False, indent=2)
    return merged


def load_user_settings() -> Dict[str, Any]:
    return _load(config.USER_SETTINGS_PATH, DEFAULT_USER_SETTINGS)


def save_user_settings(data: Dict[str, Any]) -> Dict[str, Any]:
    return _save(config.USER_SETTINGS_PATH, data, DEFAULT_USER_SETTINGS)


def load_ai_prompts() -> Dict[str, Any]:
    return _load(config.AI_PROMPTS_PATH, DEFAULT_AI_PROMPTS)


def save_ai_prompts(data: Dict[str, Any]) -> Dict[str, Any]:
    return _save(config.AI_PROMPTS_PATH, data, DEFAULT_AI_PROMPTS)


def load_expressions() -> Dict[str, Any]:
    return _load(config.EXPRESSIONS_PATH, DEFAULT_EXPRESSIONS)


def save_expressions(data: Dict[str, Any]) -> Dict[str, Any]:
    return _save(config.EXPRESSIONS_PATH, data, DEFAULT_EXPRESSIONS)
