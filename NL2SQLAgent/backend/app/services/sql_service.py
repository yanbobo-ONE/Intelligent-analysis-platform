from __future__ import annotations

import re
from typing import Any

from app.database import get_connection

_ALLOWED = re.compile(r"^\s*select\b", re.IGNORECASE)
_FORBIDDEN = re.compile(r"\b(insert|update|delete|drop|alter|truncate|create|replace|attach|detach)\b", re.IGNORECASE)


def validate_sql(sql: str) -> None:
    if not _ALLOWED.search(sql):
        raise ValueError("Only SELECT statements are allowed")
    if _FORBIDDEN.search(sql):
        raise ValueError("Forbidden SQL keyword detected")


def execute_sql(sql: str) -> list[dict[str, Any]]:
    validate_sql(sql)
    with get_connection() as conn:
        rows = conn.execute(sql).fetchall()
    return [dict(row) for row in rows]
