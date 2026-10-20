"""
silver.py — Bronze → Silver layer
- Data quality checks (log and continue)
- Cleaning & standardisation
- Derived columns
- Writes to silver_db
"""

import pandas as pd
import mysql.connector
from datetime import datetime
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from config import DB_CONFIG, BRONZE_DB, SILVER_DB

RUN_TS = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

# ------------------------------------------------------------------------------
# DDL
# ------------------------------------------------------------------------------
DDL = {
    "users": """
        CREATE TABLE IF NOT EXISTS users (
            user_id              VARCHAR(10) NOT NULL,
            signup_date          DATE,
            city_tier            VARCHAR(10),
            device_type          VARCHAR(10),
            platform             VARCHAR(5),
            acquisition_channel  VARCHAR(20),
            age_band             VARCHAR(10),
            is_returner          TINYINT(1),
            ingested_at          DATETIME,
            silver_loaded_at     DATETIME,
            PRIMARY KEY (user_id)
        )
    """,
    "events": """
        CREATE TABLE IF NOT EXISTS events (
            event_id             VARCHAR(10) NOT NULL,
            user_id              VARCHAR(10),
            session_id           VARCHAR(12),
            event_name           VARCHAR(30),
            event_timestamp      DATETIME(3),
            event_date           DATE,
            category             VARCHAR(15),
            subcategory          VARCHAR(20),
            product_id           VARCHAR(8),
            price_band           VARCHAR(10),
            search_query         VARCHAR(100),
            utm_source           VARCHAR(20),
            ingested_at          DATETIME,
            silver_loaded_at     DATETIME,
            PRIMARY KEY (event_id)
        )
    """,
    "orders": """
        CREATE TABLE IF NOT EXISTS orders (
            order_id             VARCHAR(10) NOT NULL,
            user_id              VARCHAR(10),
            order_date           DATETIME(3),
            gmv                  DECIMAL(10,2),
            gmv_band             VARCHAR(10),
            category_mix         JSON,
            payment_method       VARCHAR(10),
            coupon_applied       TINYINT(1),
            return_initiated     TINYINT(1),
            ingested_at          DATETIME,
            silver_loaded_at     DATETIME,
            PRIMARY KEY (order_id)
        )
    """,
    "data_quality_log": """
        CREATE TABLE IF NOT EXISTS data_quality_log (
            id               INT AUTO_INCREMENT PRIMARY KEY,
            run_ts           DATETIME,
            table_name       VARCHAR(20),
            rule_name        VARCHAR(60),
            failed_rows      INT,
            action_taken     VARCHAR(40)
        )
    """,
}

# ------------------------------------------------------------------------------
# helpers
# ------------------------------------------------------------------------------
def get_conn(database=None):
    cfg = DB_CONFIG.copy()
    if database:
        cfg["database"] = database
    return mysql.connector.connect(**cfg)


def batch_insert(cursor, table, df, batch_size=10_000):
    cols         = ", ".join(df.columns)
    placeholders = ", ".join(["%s"] * len(df.columns))
    sql          = f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"
    total        = len(df)
    inserted     = 0
    for start in range(0, total, batch_size):
        rows = [tuple(r) for r in df.iloc[start:start+batch_size].itertuples(index=False, name=None)]
        cursor.executemany(sql, rows)
        inserted += len(rows)
        print(f"    {inserted:,}/{total:,} rows", end="\r")
    print(f"    {inserted:,}/{total:,} rows ✓")


def log_issue(dq_rows, table, rule, failed_count, action="logged_and_continued"):
    print(f"  [DQ] {table}.{rule}: {failed_count:,} rows → {action}")
    dq_rows.append((RUN_TS, table, rule, failed_count, action))


def read_bronze(conn, table):
    return pd.read_sql(f"SELECT * FROM {table}", conn)


# ------------------------------------------------------------------------------
# quality checks
# ------------------------------------------------------------------------------
def check_users(df, dq_rows):
    # null check on critical columns
    for col in ["user_id", "signup_date", "city_tier", "device_type"]:
        n = df[col].isna().sum()
        if n: log_issue(dq_rows, "users", f"null_{col}", n)

    # duplicate user_ids
    dupes = df["user_id"].duplicated().sum()
    if dupes: log_issue(dq_rows, "users", "duplicate_user_id", dupes)
    df = df.drop_duplicates(subset="user_id", keep="first")

    # invalid city_tier values
    valid_tiers = {"tier_1","tier_2","tier_3"}
    bad = ~df["city_tier"].isin(valid_tiers)
    if bad.sum(): log_issue(dq_rows, "users", "invalid_city_tier", bad.sum())

    return df


def check_events(df, valid_user_ids, dq_rows):
    # nulls on critical columns
    for col in ["event_id","user_id","session_id","event_name","event_timestamp"]:
        n = df[col].isna().sum()
        if n: log_issue(dq_rows, "events", f"null_{col}", n)

    # duplicate event_ids
    dupes = df["event_id"].duplicated().sum()
    if dupes: log_issue(dq_rows, "events", "duplicate_event_id", dupes)
    df = df.drop_duplicates(subset="event_id", keep="first")

    # orphan events (user_id not in users)
    orphans = ~df["user_id"].isin(valid_user_ids)
    if orphans.sum(): log_issue(dq_rows, "events", "orphan_user_id", orphans.sum())

    # invalid event_name values
    valid_events = {
        "app_open","home_view","search","category_page_view","pdp_view",
        "add_to_wishlist","add_to_cart","checkout_start","payment_page",
        "order_placed","order_returned",
    }
    bad = ~df["event_name"].isin(valid_events)
    if bad.sum(): log_issue(dq_rows, "events", "invalid_event_name", bad.sum())

    return df


def check_orders(df, valid_user_ids, dq_rows):
    # nulls
    for col in ["order_id","user_id","order_date","gmv"]:
        n = df[col].isna().sum()
        if n: log_issue(dq_rows, "orders", f"null_{col}", n)

    # duplicates
    dupes = df["order_id"].duplicated().sum()
    if dupes: log_issue(dq_rows, "orders", "duplicate_order_id", dupes)
    df = df.drop_duplicates(subset="order_id", keep="first")

    # negative GMV
    neg = (df["gmv"] < 0).sum()
    if neg: log_issue(dq_rows, "orders", "negative_gmv", neg)

    # orphan orders
    orphans = ~df["user_id"].isin(valid_user_ids)
    if orphans.sum(): log_issue(dq_rows, "orders", "orphan_user_id", orphans.sum())

    return df


# ------------------------------------------------------------------------------
# transformations
# ------------------------------------------------------------------------------
def transform_users(df, orders_df):
    # standardise categoricals
    for col in ["city_tier","device_type","platform","acquisition_channel","age_band"]:
        df[col] = df[col].str.strip().str.lower()

    # derived: is_returner flag
    returners = orders_df[orders_df["return_initiated"] == 1]["user_id"].unique()
    df["is_returner"] = df["user_id"].isin(returners).astype(int)

    df["silver_loaded_at"] = RUN_TS
    return df


def transform_events(df):
    # standardise categoricals
    for col in ["event_name","category","subcategory","price_band","utm_source"]:
        if col in df.columns:
            df[col] = df[col].str.strip().str.lower()

    # derived: event_date
    df["event_timestamp"] = pd.to_datetime(df["event_timestamp"])
    df["event_date"]      = df["event_timestamp"].dt.date

    df["silver_loaded_at"] = RUN_TS
    return df


def transform_orders(df):
    # standardise
    for col in ["payment_method"]:
        df[col] = df[col].str.strip().str.upper()

    # derived: gmv_band
    df["gmv_band"] = pd.cut(
        df["gmv"],
        bins   =[0, 500, 2000, 5000, float("inf")],
        labels =["low","mid","high","premium"],
    ).astype(str)

    df["silver_loaded_at"] = RUN_TS
    return df


# ------------------------------------------------------------------------------
# type coercions for MySQL
# ------------------------------------------------------------------------------
def coerce_for_mysql(df):
    for col in ["event_timestamp","order_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col]).dt.strftime("%Y-%m-%d %H:%M:%S.%f").str[:-3]
    for col in ["signup_date","event_date"]:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col]).dt.date
    for col in ["coupon_applied","return_initiated","is_returner"]:
        if col in df.columns:
            df[col] = df[col].astype(int)
    return df.where(pd.notnull(df), None)


# ------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------
def run():
    print("=" * 55)
    print("SILVER LAYER LOAD")
    print("=" * 55)

    dq_rows = []   # accumulates (run_ts, table, rule, failed_rows, action)

    # --- read bronze ---
    print("\n[bronze] reading tables...")
    b_conn = get_conn(database=BRONZE_DB)
    users_df  = read_bronze(b_conn, "users")
    events_df = read_bronze(b_conn, "events")
    orders_df = read_bronze(b_conn, "orders")
    b_conn.close()
    print(f"  users: {len(users_df):,} | events: {len(events_df):,} | orders: {len(orders_df):,}")

    # --- quality checks ---
    print("\n[quality checks]")
    users_df  = check_users(users_df, dq_rows)
    events_df = check_events(events_df, set(users_df["user_id"]), dq_rows)
    orders_df = check_orders(orders_df, set(users_df["user_id"]), dq_rows)

    # --- transformations ---
    print("\n[transformations]")
    users_df  = transform_users(users_df, orders_df)
    events_df = transform_events(events_df)
    orders_df = transform_orders(orders_df)
    print("  all transforms applied ✓")

    # --- coerce types ---
    users_df  = coerce_for_mysql(users_df)
    events_df = coerce_for_mysql(events_df)
    orders_df = coerce_for_mysql(orders_df)

    # drop bronze-only helper column if present
    for df in [users_df, events_df, orders_df]:
        df.drop(columns=["ingested_at"], errors="ignore", inplace=True)
    # re-add ingested_at as passthrough (keep audit trail)
    users_df["ingested_at"]  = RUN_TS
    events_df["ingested_at"] = RUN_TS
    orders_df["ingested_at"] = RUN_TS

    # --- write to silver_db ---
    print("\n[silver_db] writing tables...")
    s_conn_root = get_conn()
    cur = s_conn_root.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{SILVER_DB}`")
    s_conn_root.commit()
    cur.close()
    s_conn_root.close()

    s_conn = get_conn(database=SILVER_DB)
    cur    = s_conn.cursor()

    for name, df in [("users", users_df), ("events", events_df), ("orders", orders_df)]:
        print(f"\n[{name}] inserting {len(df):,} rows...")
        cur.execute(f"DROP TABLE IF EXISTS {name}")
        cur.execute(DDL[name])
        batch_insert(cur, name, df)
        s_conn.commit()

    # --- write data quality log ---
    print("\n[data_quality_log] writing...")
    cur.execute("DROP TABLE IF EXISTS data_quality_log")
    cur.execute(DDL["data_quality_log"])
    if dq_rows:
        cur.executemany(
            "INSERT INTO data_quality_log (run_ts,table_name,rule_name,failed_rows,action_taken)"
            " VALUES (%s,%s,%s,%s,%s)", dq_rows
        )
    s_conn.commit()
    cur.close()
    s_conn.close()

    print("\n" + "=" * 55)
    print("Silver load complete.")
    print(f"Database : {SILVER_DB}")
    print(f"Tables   : users, events, orders, data_quality_log")
    print(f"DQ issues logged: {len(dq_rows)}")
    print(f"Loaded at: {RUN_TS}")
    print("=" * 55)


if __name__ == "__main__":
    run()
