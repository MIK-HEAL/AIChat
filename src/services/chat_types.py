from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ChatMessage:
    role: str
    content: str


@dataclass
class ChatCommand:
    type: str
    payload: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatResponse:
    text: str
    commands: List[ChatCommand] = field(default_factory=list)
    raw: Any | None = None
    status: str = "ok"
    error: Optional[str] = None

    def is_error(self) -> bool:
        return self.status == "error"
