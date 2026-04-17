from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class NL2SQLTrace:
    model: str
    latency_ms: int
    sql: str
    tool_calls: list[dict[str, Any]]
    streaming: bool = False


@dataclass
class NL2SQLResponse:
    answer_text: str
    table_data: list[list[Any]]
    chart_spec: dict[str, Any]
    trace: NL2SQLTrace

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["trace"] = asdict(self.trace)
        return data


DEFAULT_CHART_SPEC = {
    "type": "bar",
    "xField": "region",
    "yField": "total_amount",
    "seriesField": "region",
}
