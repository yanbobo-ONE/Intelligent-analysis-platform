from __future__ import annotations

from typing import Any


def build_chart_spec(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"type": "table", "reason": "empty-data"}

    keys = list(rows[0].keys())
    if len(keys) >= 2:
        return {
            "type": "line",
            "xField": keys[0],
            "yField": keys[1],
            "seriesField": keys[0],
        }
    return {"type": "table", "reason": "insufficient-fields"}
