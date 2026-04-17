from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from time import perf_counter
from typing import Any
from uuid import uuid4

from app.database import get_connection
from app.services.security_service import validate_readonly_sql
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_community.utilities import SQLDatabase
from nl2sql_contract import DEFAULT_CHART_SPEC, NL2SQLResponse, NL2SQLTrace
from qwen_client import bind_tools_qwen, get_qwen_model, stream_qwen
from vendor_model_client import get_vendor_model_from_config, stream_vendor_model


DEMO_SQLITE_URL = "sqlite:///E:/cursorList/智能分析系统/NL2SQLAgent/backend/demo_nl2sql.db"
ANALYTICS_HINTS = (
    "统计",
    "查询",
    "分析",
    "销售",
    "区域",
    "金额",
    "趋势",
    "top",
    "top 10",
    "前几",
    "排名",
    "sql",
    "表",
    "人数",
    "数量",
    "收入",
    "营收",
    "占比",
    "同比",
    "环比",
    "均值",
    "平均",
    "最大",
    "最小",
)
GENERAL_HINTS = (
    "你是什么模型",
    "你是哪个模型",
    "你是谁",
    "介绍一下你自己",
    "你好",
    "hi",
    "hello",
    "能做什么",
    "你会什么",
    "请介绍",
    "自我介绍",
)

NL2SQL_ONLY_NOTICE = "本项目仅支持 NL2SQL，请输入自然语言分析问题，例如：统计各区域销售额、按时间汇总订单量、查询前 3 名。"

GENERAL_PATTERNS = (
    r"^你好[，。！!\s]*$",
    r"^hi[，。！!\s]*$",
    r"^hello[，。！!\s]*$",
    r"^你(?:是|是什么|是谁|是哪一个)模型.*$",
    r"^你.*(?:是什么|是谁|是哪个)模型.*$",
    r"^介绍(?:一下)?你自己.*$",
    r"^你会(?:做|什么|哪些).*?$",
)


class QueryIntent:
    def __init__(self, limit: int = 3, sort_order: str = 'DESC', is_extreme: bool = False, extreme_type: str | None = None):
        self.limit = limit
        self.sort_order = sort_order
        self.is_extreme = is_extreme
        self.extreme_type = extreme_type


def should_use_nl2sql(user_input: str) -> bool:
    """判断是否应该走 NL2SQL 分支"""
    sql_keywords = [
        "查询", "统计", "分析", "汇总", "列出", "返回", "找出", "获取",
        "销售额", "销售", "金额", "数量", "价格", "单价", "成本", "利润",
        "前", "top", "排名", "排序", "按", "分组", "平均", "最大", "最小", "总和",
        "条", "行", "记录", "数据", "报表", "进度", "完成率"
    ]

    lower_input = (user_input or "").lower()

    for kw in sql_keywords:
        if kw in lower_input:
            return True

    if re.search(r"\d+\s*[条行个]", lower_input):
        return True

    return False

CN_NUM_MAP = {
    "零": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
    "十": 10,
}

LIMIT_PATTERNS = (
    r"(?:前|top\s*)(\d+)",
    r"(?:返回|取|只要|给我)(\d+)(?:条|名|个|项)?",
    r"(?:top|TOP)\s*(\d+)",
    r"前([一二两三四五六七八九十])(?:条|名|个|项)?",
    r"(?:返回|取|只要|给我)前([一二两三四五六七八九十])(?:条|名|个|项)?",
    r"(最大|最小|最高|最低)的?(?:那)?(?:条|个|个数据|条数据|条记录|个记录)?",
    r"(最后|末尾|倒数第|倒数)第?([一二两三四五六七八九十1-9\d]*)?(?:条|个|个数据|条数据|条记录|个记录|的数据|的结果|的数据集)?",
    r"(?:最后一个|最后一条|最后一个数据|最后一条数据|最后一个结果|最后一条结果)",
    r"(?:末尾一个|末尾一条|末尾一个数据|末尾一条数据|末尾一个结果|末尾一条结果|末尾的数据)",
    r"(?:倒数第一个|倒数第一条|倒数第一个数据|倒数第一条数据|倒数第一个结果|倒数第一条结果)",
    r"(?:第一条|第一条数据|第一个|第一个数据|第1条|第1个|第一个结果)",
)


def _cn_number_to_int(token: str) -> int | None:
    if not token:
        return None
    if token.isdigit():
        return int(token)
    if token in CN_NUM_MAP:
        return CN_NUM_MAP[token]
    if token in {"最后", "末尾", "倒数第", "倒数", "第", "最"}:
        return 1
    if token == "十":
        return 10
    if len(token) == 2 and token[0] == "十" and token[1] in CN_NUM_MAP:
        return 10 + CN_NUM_MAP[token[1]]
    if len(token) == 2 and token[1] == "十" and token[0] in CN_NUM_MAP:
        return CN_NUM_MAP[token[0]] * 10
    return None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _llm_content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict):
                text = item.get("text")
                if text:
                    parts.append(str(text))
            elif isinstance(item, str):
                parts.append(item)
        return "".join(parts)
    return str(content or "")


def _looks_like_general_chat(message: str) -> bool:
    text = (message or "").strip().lower()
    if not text:
        return True
    if any(hint in text for hint in GENERAL_HINTS):
        return True
    return any(re.search(pattern, text) for pattern in GENERAL_PATTERNS)


def _parse_query_intent(message: str) -> QueryIntent:
    text = (message or '').strip().lower()
    intent = QueryIntent()

    # 默认排序方向
    if any(keyword in text for keyword in ('从低到高', '最小', '最低', '升序', 'asc')):
        intent.sort_order = 'ASC'
    if any(keyword in text for keyword in ('从高到低', '最大', '最高', '降序', 'desc', '排名靠前', 'top')):
        intent.sort_order = 'DESC'

    # 单条极值/位置规则
    if re.search(r'(最大|最小|最高|最低)的?(?:那)?(?:条|个|条数据|个数据|条记录|个记录)?', text):
        intent.is_extreme = True
        intent.extreme_type = 'max' if any(k in text for k in ('最大', '最高')) else 'min'
        intent.limit = 1
    elif any(phrase in text for phrase in ('最后一条', '最后一个', '倒数第一个', '倒数第一条', '末尾一条', '末尾一个', '第一个', '第一条', '第1个', '第1条')):
        intent.limit = 1
        if any(phrase in text for phrase in ('末尾', '最小')):
            intent.sort_order = 'ASC'

    # 明确数字/中文数字
    for pattern in LIMIT_PATTERNS:
        match = re.search(pattern, text)
        if match:
            values = [g for g in match.groups() if g]
            if values:
                parsed = _cn_number_to_int(values[-1])
                if parsed is not None:
                    intent.limit = parsed
                    break
            else:
                intent.limit = 1
                break

    return intent


def _looks_like_analytics_question(message: str) -> bool:
    text = (message or "").strip().lower()
    if not text:
        return False
    if should_use_nl2sql(text):
        return True
    if _looks_like_general_chat(text):
        return False
    if any(hint in text for hint in ANALYTICS_HINTS):
        return True
    if any(re.search(pattern, text) for pattern in LIMIT_PATTERNS):
        return True
    if len(text) >= 18 and any(token in text for token in ("数据", "表", "字段", "指标", "分组", "按", "查询", "统计", "销售额", "金额")):
        return True
    return False


def save_message(session_id: str, role: str, content: str) -> None:
    msg_id = str(uuid4())
    now = _now()
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO chat_messages (id, session_id, role, content, created_at) VALUES (?, ?, ?, ?, ?)",
            (msg_id, session_id, role, content, now),
        )
        conn.execute(
            "UPDATE chat_sessions SET updated_at = ? WHERE id = ?",
            (now, session_id),
        )
        conn.commit()


def get_recent_messages(session_id: str, limit: int = 6) -> list[dict[str, str]]:
    with get_connection() as conn:
        rows = conn.execute(
            """
            SELECT role, content
            FROM chat_messages
            WHERE session_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (session_id, limit),
        ).fetchall()
    return [{"role": row[0], "content": row[1]} for row in reversed(rows)]


def _get_chat_llm(model_name: str | None = None, base_url: str | None = None, api_key: str | None = None):
    resolved_model = (model_name or "").strip()
    resolved_base_url = (base_url or "").strip()
    resolved_api_key = (api_key or "").strip()

    if resolved_model.lower() == "qwen3-max" and not resolved_api_key and not resolved_base_url:
        return get_qwen_model()

    if resolved_api_key or resolved_base_url:
        return get_vendor_model_from_config(
            resolved_base_url or os.getenv("VENDOR_BASE_URL", "https://cpa.haitim.cn/v1"),
            resolved_model or os.getenv("VENDOR_MODEL", "gpt-5.3-codex"),
            resolved_api_key or os.getenv("VENDOR_API_KEY", os.getenv("DASHSCOPE_API_KEY", "")),
        )

    return get_qwen_model()


def build_nl2sql_response(question: str, model_name: str | None = None, base_url: str | None = None, api_key: str | None = None) -> dict[str, Any]:
    start = perf_counter()
    llm = _get_chat_llm(model_name=model_name, base_url=base_url, api_key=api_key)
    db = SQLDatabase.from_uri(DEMO_SQLITE_URL)

    schema_info = db.get_table_info()
    intent = _parse_query_intent(question)
    limit_hint = intent.limit
    sort_order = intent.sort_order
    extreme_clause = ''
    if intent.is_extreme:
        extreme_clause = '，并返回单条极值记录'

    prompt = f"""
你是一个 NL2SQL 组件，请只输出 SQL，不要解释。

数据库表结构：
{schema_info}

问题：{question}

解析意图：
- 结果条数：{limit_hint}
- 排序方向：{sort_order}
- 极值模式：{'是' if intent.is_extreme else '否'}{extreme_clause}

输出要求：
1. 只输出 SQLite SELECT SQL
2. 需要包含 GROUP BY
3. 需要按金额{('降序' if sort_order == 'DESC' else '升序')}
4. 只返回前 {limit_hint} 条
""".strip()

    sql_response = llm.invoke(prompt)
    generated_sql = _llm_content_to_text(getattr(sql_response, 'content', '')).strip().strip("```sql").strip("```").strip()
    if limit_hint:
        if re.search(r"(?i)\blimit\s+\d+\b", generated_sql):
            generated_sql = re.sub(r"(?i)\blimit\s+\d+\b", f"LIMIT {limit_hint}", generated_sql)
        elif re.search(r";\s*$", generated_sql):
            generated_sql = re.sub(r";\s*$", f" LIMIT {limit_hint};", generated_sql)
        else:
            generated_sql = f"{generated_sql} LIMIT {limit_hint}"

    if intent.is_extreme and intent.sort_order == 'ASC':
        generated_sql = re.sub(r'ORDER\s+BY\s+[^\n]+DESC', 'ORDER BY total_amount ASC', generated_sql, flags=re.IGNORECASE)

    validate_readonly_sql(generated_sql)
    rows = db.run(generated_sql)
    rows_text = str(rows).strip()
    table_data: list[list[Any]] = []
    if rows_text:
        if rows_text.startswith('[') and rows_text.endswith(']'):
            rows_text = rows_text[1:-1]
        raw_rows = [part.strip() for part in re.split(r"\)\s*,\s*\(", rows_text.replace('\n', ' ')) if part.strip()]
        if not raw_rows and rows_text:
            raw_rows = [rows_text]
        for item in raw_rows[:limit_hint]:
            cleaned = item.strip().strip('()')
            parts = [p.strip().strip("'") for p in cleaned.split(',') if p.strip()]
            if len(parts) >= 2:
                table_data.append([parts[0], parts[1]])
            elif len(parts) == 1:
                table_data.append([parts[0], 0])

    actual_limit = len(table_data) if table_data else limit_hint
    if table_data:
        preview_names = [str(row[0]) for row in table_data[:3] if row and row[0] is not None]
        preview_text = "、".join(preview_names)
        if preview_text:
            answer_text = f"已查询到 {actual_limit} 条结果，分别是{preview_text}，请查看图表和表格。"
        else:
            answer_text = f"已查询到 {actual_limit} 条结果，请查看图表和表格。"
    else:
        answer_text = "未查询到结果，请调整查询条件。"

    latency_ms = int((perf_counter() - start) * 1000)
    response = NL2SQLResponse(
        answer_text=answer_text,
        table_data=table_data,
        chart_spec=DEFAULT_CHART_SPEC,
        trace=NL2SQLTrace(
            model=model_name or os.getenv("VENDOR_MODEL", os.getenv("QWEN_MODEL", "qwen3-max")),
            latency_ms=latency_ms,
            sql=generated_sql,
            tool_calls=[
                {
                    "name": "sql_db_query",
                    "args": {"query": generated_sql},
                    "result": rows,
                }
            ],
            streaming=False,
        ),
    )
    return response.to_dict()


def build_general_response(message: str, model_name: str | None = None, base_url: str | None = None, api_key: str | None = None, session_id: str | None = None) -> dict[str, Any]:
    start = perf_counter()
    recent_messages = get_recent_messages(session_id) if session_id else []
    context_lines = []
    for item in recent_messages:
        role_label = "用户" if item["role"] == "user" else "助手"
        context_lines.append(f"{role_label}: {item['content']}")
    context = "\n".join(context_lines).strip()
    prompt = message if not context else f"以下是最近对话上下文：\n{context}\n\n当前用户问题：{message}"
    answer = NL2SQL_ONLY_NOTICE if message else NL2SQL_ONLY_NOTICE
    latency_ms = int((perf_counter() - start) * 1000)
    response = NL2SQLResponse(
        answer_text=answer,
        table_data=[],
        chart_spec=DEFAULT_CHART_SPEC,
        trace=NL2SQLTrace(
            model=model_name or os.getenv("VENDOR_MODEL", os.getenv("QWEN_MODEL", "qwen3-max")),
            latency_ms=latency_ms,
            sql="",
            tool_calls=[],
            streaming=False,
        ),
    )
    return response.to_dict()


def build_response(message: str, model_name: str | None = None, base_url: str | None = None, api_key: str | None = None, session_id: str | None = None) -> dict:
    analytics = _looks_like_analytics_question(message)
    general = _looks_like_general_chat(message)
    print(f'[chat_service] message={message!r} analytics={analytics} general={general}')
    if analytics:
        print('[chat_service] branch=nl2sql')
        return build_nl2sql_response(message, model_name=model_name, base_url=base_url, api_key=api_key)
    print('[chat_service] branch=general')
    return build_general_response(message, model_name=model_name, base_url=base_url, api_key=api_key, session_id=session_id)


def build_stream(message: str, model_name: str | None = None, base_url: str | None = None, api_key: str | None = None):
    if model_name or base_url or api_key:
        return stream_vendor_model(message, base_url=base_url, model_name=model_name, api_key=api_key)
    return stream_qwen(message)


def build_tool_llm(tools: list):
    return bind_tools_qwen(tools)
