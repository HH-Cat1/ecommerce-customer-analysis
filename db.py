"""SQLite persistence for imported order data."""

from contextlib import closing
from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "data" / "ecommerce.db"

ORDER_COLUMNS = [
    "order_id", "order_date", "customer_id", "product_name", "category",
    "quantity", "unit_price", "channel", "region",
]


def get_connection():
    import sqlite3

    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH, timeout=15)
    connection.execute("PRAGMA journal_mode=WAL")
    return connection


def initialize_database() -> None:
    with closing(get_connection()) as connection:
        connection.execute(
            """CREATE TABLE IF NOT EXISTS orders (
                line_id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                order_date TEXT NOT NULL,
                customer_id TEXT NOT NULL,
                product_name TEXT NOT NULL,
                category TEXT NOT NULL,
                quantity REAL NOT NULL CHECK (quantity > 0),
                unit_price REAL NOT NULL CHECK (unit_price >= 0),
                channel TEXT NOT NULL,
                region TEXT NOT NULL
            )"""
        )
        connection.execute("CREATE INDEX IF NOT EXISTS idx_orders_date ON orders(order_date)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_orders_category ON orders(category)")
        connection.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id)")
        connection.commit()


def order_count() -> int:
    with closing(get_connection()) as connection:
        row = connection.execute("SELECT COUNT(*) FROM orders").fetchone()
    return int(row[0])


def replace_orders(frame: pd.DataFrame) -> int:
    missing = set(ORDER_COLUMNS) - set(frame.columns)
    if missing:
        raise ValueError("缺少必要字段：" + "、".join(sorted(missing)))

    values = frame[ORDER_COLUMNS].copy()
    values["order_date"] = pd.to_datetime(values["order_date"], errors="coerce").dt.strftime("%Y-%m-%d %H:%M:%S")
    values = values.dropna(subset=ORDER_COLUMNS)
    rows = [
        tuple(value.item() if hasattr(value, "item") else value for value in row)
        for row in values.itertuples(index=False, name=None)
    ]
    with closing(get_connection()) as connection:
        with connection:
            connection.execute("DELETE FROM orders")
            connection.executemany(
                """INSERT INTO orders (
                    order_id, order_date, customer_id, product_name, category,
                    quantity, unit_price, channel, region
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                rows,
            )
    return len(rows)


def read_orders() -> pd.DataFrame:
    with closing(get_connection()) as connection:
        frame = pd.read_sql_query(
            """SELECT order_id, order_date, customer_id, product_name, category,
                      quantity, unit_price, channel, region,
                      quantity * unit_price AS revenue
               FROM orders""",
            connection,
        )
    frame["order_date"] = pd.to_datetime(frame["order_date"], errors="coerce")
    return frame

