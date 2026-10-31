"""Natural-language analytics using OpenAI Responses and read-only SQLite SQL."""

from __future__ import annotations

import json
import os
import re
import sqlite3
import time
from pathlib import Path

import pandas as pd
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).parent / ".env")

MODEL = os.getenv("OPENAI_MODEL", "gpt-5.5")
MAX_ROWS = 100
ALLOWED_ACTIONS = {
    sqlite3.SQLITE_SELECT,
    sqlite3.SQLITE_READ,
    sqlite3.SQLITE_FUNCTION,
}
if hasattr(sqlite3, "SQLITE_RECURSIVE"):
    ALLOWED_ACTIONS.add(sqlite3.SQLITE_RECURSIVE)


def _authorizer(action: int, arg1: str | None, arg2: str | None, _db: str | None, _source: str | None) -> int:
    if action not in ALLOWED_ACTIONS:
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_READ and arg1 != "orders":
        return sqlite3.SQLITE_DENY
    if action == sqlite3.SQLITE_FUNCTION:
        function_name = (arg2 or arg1 or "").lower()
        allowed_functions = {
            "abs", "avg", "coalesce", "count", "date", "datetime", "ifnull",
            "julianday", "lower", "max", "min", "nullif", "round", "strftime",
            "substr", "sum", "time", "total", "upper",
        }
        if function_name not in allowed_functions:
            return sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK


def _clean_sql(text: str) -> str:
    match = re.search(r"```(?:sql)?\s*(.*?)```", text, flags=re.IGNORECASE | re.DOTALL)
    sql = match.group(1).strip() if match else text.strip()
    sql = re.sub(r"^\s*SQL\s*:\s*", "", sql, flags=re.IGNORECASE)
    sql = sql.removesuffix(";").strip()
    if len(sql) > 3000:
        raise ValueError("生成的查询过长，请换个更具体的问题。")
    if not re.match(r"(?is)^(SELECT|WITH)\b", sql):
        raise ValueError("模型没有生成只读查询，请换一种问法。")
    if ";" in sql or "--" in sql or "/*" in sql or "*/" in sql:
        raise ValueError("查询包含不支持的语句或注释，已拒绝执行。")
    safe_count_sql = re.sub(
        r"COUNT\s*\(\s*DISTINCT\s+(customer_id|order_id)\s*\)",
        "COUNT_DISTINCT_ID()",
        sql,
        flags=re.IGNORECASE,
    )
    if re.search(r"\b(customer_id|order_id)\b", safe_count_sql, flags=re.IGNORECASE):
        raise ValueError("为保护订单和客户标识，只允许统计其去重数量，不能查询原始编号。")
    return sql


def _run_read_only_query(sql: str, frame: pd.DataFrame) -> pd.DataFrame:
    connection = sqlite3.connect(":memory:")
    try:
        frame[[
            "order_id", "order_date", "customer_id", "product_name", "category",
            "quantity", "unit_price", "channel", "region", "revenue",
        ]].to_sql("orders", connection, index=False, if_exists="replace")
        connection.set_authorizer(_authorizer)
        deadline = time.monotonic() + 2
        connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        if not re.search(r"\bLIMIT\b", sql, flags=re.IGNORECASE):
            sql = f"{sql} LIMIT {MAX_ROWS}"
        cursor = connection.execute(sql)
        columns = [item[0] for item in cursor.description or []]
        rows = cursor.fetchmany(MAX_ROWS + 1)
        if len(rows) > MAX_ROWS:
            raise ValueError(f"结果超过 {MAX_ROWS} 行，请缩小查询范围或增加聚合。")
        return pd.DataFrame(rows, columns=columns)
    except sqlite3.Error as error:
        raise ValueError(f"只读 SQL 查询失败：{error}") from error
    finally:
        connection.close()


def answer_question(question: str, frame: pd.DataFrame, api_key: str | None = None) -> tuple[str, str, pd.DataFrame]:
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        raise ValueError("未配置 OPENAI_API_KEY。请复制 .env.example 为 .env 并填入 API 密钥。")

    client = OpenAI(api_key=key)
    schema = """SQLite 表 orders（当前页面筛选后的订单明细）：
order_id TEXT 订单编号；order_date TEXT 下单时间；customer_id TEXT 客户编号；
product_name TEXT 商品名称；category TEXT 品类；quantity REAL 数量；unit_price REAL 单价；
channel TEXT 渠道；region TEXT 地区；revenue REAL 销售额（数量 × 单价）。"""
    sql_response = client.responses.create(
        model=MODEL,
        store=False,
        instructions=(
            "你是电商数据分析 SQL 生成器。根据用户问题生成一条 SQLite 只读 SELECT 查询。"
            "只能查询 orders 表和列出的字段；销售额用 revenue；订单数用 COUNT(DISTINCT order_id)。"
            "customer_id 和 order_id 只能用于 COUNT(DISTINCT ...)，不能返回原始编号。"
            "禁止写入、修改、删除数据，禁止访问其他表或系统信息。结果优先聚合并限制在 100 行内。"
            "只输出 SQL，不要解释，不要 Markdown。"
        ),
        input=f"{schema}\n\n用户问题：{question}",
        max_output_tokens=300,
    )
    sql = _clean_sql(sql_response.output_text)
    result = _run_read_only_query(sql, frame)
    result_payload = json.dumps(result.to_dict(orient="records"), ensure_ascii=False, default=str)

    answer_response = client.responses.create(
        model=MODEL,
        store=False,
        instructions=(
            "你是电商经营分析助手。只根据提供的查询结果回答用户问题；"
            "明确指出数值口径，不要编造数据。结果为空时说明当前筛选范围没有匹配记录。"
            "使用简洁中文回答，并在必要时提供一条可执行的经营观察。"
        ),
        input=f"用户问题：{question}\n查询结果 JSON：{result_payload}",
        max_output_tokens=500,
    )
    return answer_response.output_text, sql, result

