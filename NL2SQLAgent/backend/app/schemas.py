from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class SessionCreate:
    title: str


@dataclass
class SessionUpdate:
    title: str


@dataclass
class ChatRequest:
    session_id: str
    message: str


@dataclass
class ChatResponse:
    answer_text: str
    table_data: list[dict[str, Any]]
    chart_spec: dict[str, Any]
    trace: dict[str, Any]
