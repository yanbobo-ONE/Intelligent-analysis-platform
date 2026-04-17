from __future__ import annotations

import re

FORBIDDEN_SQL_PATTERNS = [
    r"\binsert\b",
    r"\bupdate\b",
    r"\bdelete\b",
    r"\bdrop\b",
    r"\balter\b",
    r"\bcreate\b",
    r"\btruncate\b",
    r"\breplace\b",
]


def ensure_read_only(sql: str) -> None:
    normalized = sql.lower()
    if not normalized.strip().startswith("select"):
        raise ValueError("Only SELECT statements are allowed")
    for pattern in FORBIDDEN_SQL_PATTERNS:
        if re.search(pattern, normalized):
            raise ValueError("Forbidden SQL detected")
