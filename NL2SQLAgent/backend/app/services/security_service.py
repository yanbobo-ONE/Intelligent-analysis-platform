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
    r"\battach\b",
    r"\bdetach\b",
]

ALLOWED_PREFIX = ("select", "with")


def validate_readonly_sql(sql: str) -> None:
    normalized = sql.strip().lower()
    if not normalized.startswith(ALLOWED_PREFIX):
        raise ValueError("Only SELECT/WITH queries are allowed")

    for pattern in FORBIDDEN_SQL_PATTERNS:
        if re.search(pattern, normalized, flags=re.IGNORECASE):
            raise ValueError("Forbidden SQL keyword detected")
