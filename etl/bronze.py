"""
bronze.py — Load raw Parquet files into bronze_db (MySQL)
Tables: bronze_db.users, bronze_db.events, bronze_db.orders
No transformations — raw landing zone only.
Adds ingested_at metadata column.
"""

import pandas as pd
import mysql.connector
from mysql.connector import Error
from datetime import datetime
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))
from config import DB_CONFIG, BRONZE_DB, BRONZE_DIR

INGESTED_AT = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ------------------------------------------------------------------------------
# DDL — bronze_db table definitions
# ------------------------------------------------------------------------------
DDL = {
    "users": """
        CREATE TABLE IF NOT EXISTS users (
            user_id             VARCHAR(10)  NOT NULL,
            signup_date         DATE,
            city_tier           VARCHAR(10),
            device_type         VARCHAR(10),
            platform            VARCHAR(5),
            acquisition_channel VARCHAR(20),
            age_band            VARCHAR(10),
            ingested_at         DATETIME,
            PRIMARY KEY (user_id)
        )
    """,
    "events": """
        CREATE TABLE IF NOT EXISTS events (
            event_id            VARCHAR(10)  NOT NULL,
            user_id             VARCHAR(10),
            session_id          VARCHAR(12),
            event_name          VARCHAR(30),
            event_timestamp     DATETIME(3),
            category            VARCHAR(15),
            subcategory         VARCHAR(20),
            product_id          VARCHAR(8),
            price_band          VARCHAR(10),
            search_query        VARCHAR(100),
            utm_source          VARCHAR(20),
            ingested_at         DATETIME,
            PRIMARY KEY (event_id)
        )
    """,
    "orders": """
        CREATE TABLE IF NOT EXISTS orders (
            order_id            VARCHAR(10)  NOT NULL,
            user_id             VARCHAR(10),
            order_date          DATETIME(3),
            gmv                 DECIMAL(10,2),
            category_mix        JSON,
            payment_method      VARCHAR(10),
            coupon_applied      TINYINT(1),
            return_initiated    TINYINT(1),
            ingested_at         DATETIME,
            PRIMARY KEY (order_id)
        )
    """,
}

# ------------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------------
def get_connection(database=None):
    cfg = DB_CONFIG.copy()
    if database:
        cfg["database"] = database
    return mysql.connector.connect(**cfg)


def create_database(cursor, db_name):
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")
    print(f"  database `{db_name}` ready")


def batch_insert(cursor, table: str, df: pd.DataFrame, batch_size: int = 10_000):
    """Insert DataFrame into MySQL in batches to respect max_allowed_packet."""
    cols    = ", ".join(df.columns)
    placeholders = ", ".join(["%s"] * len(df.columns))
    sql     = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
    total   = len(df)
    inserted = 0
    for start in range(0, total, batch_size):
        batch = df.iloc[start: start + batch_size]
        rows  = [tuple(r) for r in batch.itertuples(index=False, name=None)]
        cursor.executemany(sql, rows)
        inserted += len(rows)
        print(f"    {inserted:,}/{total:,} rows", end="\r")
    print(f"    {inserted:,}/{total:,} rows ✓")


# ------------------------------------------------------------------------------
# load
# ------------------------------------------------------------------------------
def load_table(conn, table_name: str, parquet_path: str):
    print(f"\n[{table_name}] reading parquet...")
    df = pd.read_parquet(parquet_path)
    df["ingested_at"] = INGESTED_AT

    # type coercions for MySQL compatibility
    if "signup_date" in df.columns:
        df["signup_date"] = pd.to_datetime(df["signup_date"]).dt.date
    for col in ["event_timestamp", "order_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col]).dt.strftime("%Y-%m-%d %H:%M:%S.%f").str[:-3]
    for col in ["coupon_applied", "return_initiated"]:
        if col in df.columns:
            df[col] = df[col].astype(int)
    # replace NaN with None so MySQL gets NULL
    df = df.where(pd.notnull(df), None)

    cursor = conn.cursor()
    print(f"[{table_name}] dropping and recreating table...")
    cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
    cursor.execute(DDL[table_name])

    print(f"[{table_name}] inserting {len(df):,} rows in batches...")
    batch_insert(cursor, table_name, df)
    conn.commit()
    cursor.close()
    print(f"[{table_name}] done ✓")


def run():
    print("=" * 55)
    print("BRONZE LAYER LOAD")
    print("=" * 55)

    # 1. create bronze_db
    print("\n[setup] creating bronze_db...")
    conn_root = get_connection()
    cur = conn_root.cursor()
    create_database(cur, BRONZE_DB)
    conn_root.commit()
    cur.close()
    conn_root.close()

    # 2. connect to bronze_db and load tables
    conn = get_connection(database=BRONZE_DB)
    try:
        load_table(conn, "users",  f"{BRONZE_DIR}/users.parquet")
        load_table(conn, "events", f"{BRONZE_DIR}/events.parquet")
        load_table(conn, "orders", f"{BRONZE_DIR}/orders.parquet")
    finally:
        conn.close()

    print("\n" + "=" * 55)
    print("Bronze load complete.")
    print(f"Database : {BRONZE_DB}")
    print(f"Tables   : users, events, orders")
    print(f"Loaded at: {INGESTED_AT}")
    print("=" * 55)


if __name__ == "__main__":
    run()
