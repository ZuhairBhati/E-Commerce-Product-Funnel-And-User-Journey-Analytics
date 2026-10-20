"""
gold.py — Silver → Gold layer
Builds 5 analytical tables in gold_db from silver_db data.
"""

import pandas as pd
import mysql.connector
from datetime import datetime
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from config import DB_CONFIG, SILVER_DB, GOLD_DB

RUN_TS = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

FUNNEL_ORDER = [
    "app_open","home_view","search","category_page_view","pdp_view",
    "add_to_wishlist","add_to_cart","checkout_start","payment_page",
    "order_placed","order_returned",
]

# ------------------------------------------------------------------------------
# DDL
# ------------------------------------------------------------------------------
DDL = {
    "funnel_summary": """
        CREATE TABLE IF NOT EXISTS funnel_summary (
            step_order          INT,
            event_name          VARCHAR(30),
            unique_users        INT,
            conversion_rate_pct DECIMAL(5,2),
            dropoff_rate_pct    DECIMAL(5,2),
            gold_loaded_at      DATETIME,
            PRIMARY KEY (event_name)
        )
    """,
    "segment_dropoff": """
        CREATE TABLE IF NOT EXISTS segment_dropoff (
            id                  INT AUTO_INCREMENT PRIMARY KEY,
            dimension           VARCHAR(30),
            dimension_value     VARCHAR(30),
            users_at_category   INT,
            users_at_pdp        INT,
            conversion_rate_pct DECIMAL(5,2),
            dropoff_rate_pct    DECIMAL(5,2),
            gold_loaded_at      DATETIME
        )
    """,
    "cohort_retention": """
        CREATE TABLE IF NOT EXISTS cohort_retention (
            id                  INT AUTO_INCREMENT PRIMARY KEY,
            signup_cohort_week  VARCHAR(20),
            activity_week       INT,
            cohort_size         INT,
            retained_users      INT,
            retention_rate_pct  DECIMAL(5,2),
            gold_loaded_at      DATETIME
        )
    """,
    "time_to_convert": """
        CREATE TABLE IF NOT EXISTS time_to_convert (
            user_id             VARCHAR(10) NOT NULL,
            first_seen_date     DATE,
            order_date          DATE,
            days_to_convert     INT,
            sessions_to_convert INT,
            category            VARCHAR(15),
            gold_loaded_at      DATETIME,
            PRIMARY KEY (user_id)
        )
    """,
    "gmv_by_segment": """
        CREATE TABLE IF NOT EXISTS gmv_by_segment (
            id                  INT AUTO_INCREMENT PRIMARY KEY,
            city_tier           VARCHAR(10),
            device_type         VARCHAR(10),
            payment_method      VARCHAR(10),
            category            VARCHAR(15),
            total_orders        INT,
            avg_gmv             DECIMAL(10,2),
            total_gmv           DECIMAL(14,2),
            return_rate_pct     DECIMAL(5,2),
            gold_loaded_at      DATETIME
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


def read_silver(conn, table, cols="*"):
    return pd.read_sql(f"SELECT {cols} FROM {table}", conn)


def write_table(cur, conn, name, df):
    print(f"\n[{name}] writing {len(df):,} rows...")
    cur.execute(f"DROP TABLE IF EXISTS {name}")
    cur.execute(DDL[name])
    cols         = ", ".join(df.columns)
    placeholders = ", ".join(["%s"] * len(df.columns))
    sql          = f"INSERT INTO {name} ({cols}) VALUES ({placeholders})"
    rows         = [tuple(r) for r in df.itertuples(index=False, name=None)]
    cur.executemany(sql, rows)
    conn.commit()
    print(f"  done ✓")


# ------------------------------------------------------------------------------
# gold builds
# ------------------------------------------------------------------------------
def build_funnel_summary(events_df):
    print("[funnel_summary] building...")
    counts = (
        events_df.groupby("event_name")["user_id"]
        .nunique()
        .reindex(FUNNEL_ORDER)
        .reset_index()
    )
    counts.columns = ["event_name", "unique_users"]
    counts["step_order"] = range(1, len(counts)+1)

    # step-over-step conversion vs previous step
    counts["conversion_rate_pct"] = None
    counts["dropoff_rate_pct"]    = None
    for i in range(1, len(counts)):
        prev = counts.loc[i-1, "unique_users"]
        curr = counts.loc[i,   "unique_users"]
        if prev and prev > 0:
            conv = round(curr / prev * 100, 2)
            counts.loc[i, "conversion_rate_pct"] = conv
            counts.loc[i, "dropoff_rate_pct"]    = round(100 - conv, 2)

    counts["gold_loaded_at"] = RUN_TS
    return counts[["step_order","event_name","unique_users",
                   "conversion_rate_pct","dropoff_rate_pct","gold_loaded_at"]]


def build_segment_dropoff(events_df, users_df):
    print("[segment_dropoff] building...")
    cat_users = set(events_df[events_df["event_name"]=="category_page_view"]["user_id"])
    pdp_users = set(events_df[events_df["event_name"]=="pdp_view"]["user_id"])

    ev_users = events_df[["user_id"]].drop_duplicates()
    ev_users = ev_users.merge(users_df[["user_id","device_type","acquisition_channel",
                                        "city_tier","age_band"]], on="user_id", how="left")
    # add price_band from pdp events
    pdp_price = (
        events_df[events_df["event_name"]=="pdp_view"][["user_id","price_band"]]
        .drop_duplicates("user_id")
    )
    ev_users = ev_users.merge(pdp_price, on="user_id", how="left")

    rows = []
    dims = {
        "device_type":          ev_users["device_type"],
        "acquisition_channel":  ev_users["acquisition_channel"],
        "city_tier":            ev_users["city_tier"],
        "age_band":             ev_users["age_band"],
        "price_band":           ev_users["price_band"],
    }
    for dim_name, dim_series in dims.items():
        ev_users["_dim"] = dim_series
        for val, grp in ev_users.groupby("_dim"):
            uids      = set(grp["user_id"])
            at_cat    = len(uids & cat_users)
            at_pdp    = len(uids & pdp_users)
            conv      = round(at_pdp / at_cat * 100, 2) if at_cat else 0
            rows.append((dim_name, str(val), at_cat, at_pdp,
                         conv, round(100-conv,2), RUN_TS))

    return pd.DataFrame(rows, columns=[
        "dimension","dimension_value","users_at_category","users_at_pdp",
        "conversion_rate_pct","dropoff_rate_pct","gold_loaded_at"
    ])


def build_cohort_retention(users_df, orders_df):
    print("[cohort_retention] building...")
    users_df  = users_df.copy()
    orders_df = orders_df.copy()

    users_df["signup_week"]  = pd.to_datetime(users_df["signup_date"]).dt.strftime("%Y-W%V")
    orders_df["order_week"]  = pd.to_datetime(orders_df["order_date"]).dt.strftime("%Y-W%V")

    cohort_size = users_df.groupby("signup_week")["user_id"].nunique().rename("cohort_size")

    merged = orders_df.merge(users_df[["user_id","signup_week"]], on="user_id", how="left")

    # weeks since signup
    week_map = {w: i for i, w in enumerate(sorted(users_df["signup_week"].unique()))}
    merged["signup_week_num"] = pd.to_datetime(merged["signup_week"] + "-1", format="%Y-W%W-%w").apply(lambda d: d.toordinal() // 7)
    merged["order_week_num"]  = pd.to_datetime(merged["order_week"]  + "-1", format="%Y-W%W-%w").apply(lambda d: d.toordinal() // 7)
    merged["weeks_since"]     = merged["order_week_num"] - merged["signup_week_num"]
    merged = merged[merged["weeks_since"] >= 0]

    retained = (
        merged.groupby(["signup_week","weeks_since"])["user_id"]
        .nunique()
        .reset_index()
        .rename(columns={"user_id":"retained_users","weeks_since":"activity_week"})
    )
    retained = retained.merge(cohort_size, on="signup_week")
    retained["retention_rate_pct"] = (retained["retained_users"] / retained["cohort_size"] * 100).round(2)
    retained["gold_loaded_at"]     = RUN_TS
    retained = retained.rename(columns={"signup_week":"signup_cohort_week"})
    return retained[["signup_cohort_week","activity_week","cohort_size",
                      "retained_users","retention_rate_pct","gold_loaded_at"]]


def build_time_to_convert(events_df, orders_df):
    print("[time_to_convert] building...")
    first_seen = (
        events_df[events_df["event_name"]=="app_open"]
        .groupby("user_id")["event_timestamp"]
        .min()
        .reset_index()
        .rename(columns={"event_timestamp":"first_seen_date"})
    )
    first_seen["first_seen_date"] = pd.to_datetime(first_seen["first_seen_date"]).dt.date

    first_order = (
        orders_df.sort_values("order_date")
        .drop_duplicates("user_id", keep="first")[["user_id","order_date"]]
    )
    first_order["order_date"] = pd.to_datetime(first_order["order_date"]).dt.date

    # session count per user before first order
    sess_counts = (
        events_df.merge(first_order, on="user_id")
        .query("event_timestamp <= order_date")
        .groupby("user_id")["session_id"]
        .nunique()
        .reset_index()
        .rename(columns={"session_id":"sessions_to_convert"})
    )

    # primary category from orders
    orders_df["_cat"] = orders_df["category_mix"].apply(
        lambda s: list(__import__("json").loads(s).keys())[0]
    )
    cat_map = orders_df.drop_duplicates("user_id")[["user_id","_cat"]]

    df = first_seen.merge(first_order, on="user_id", how="inner")
    df = df.merge(sess_counts, on="user_id", how="left")
    df = df.merge(cat_map,     on="user_id", how="left")
    df["days_to_convert"] = (
        pd.to_datetime(df["order_date"]) - pd.to_datetime(df["first_seen_date"])
    ).dt.days
    df["gold_loaded_at"] = RUN_TS
    df = df.rename(columns={"_cat":"category"})
    return df[["user_id","first_seen_date","order_date","days_to_convert",
               "sessions_to_convert","category","gold_loaded_at"]]


def build_gmv_by_segment(orders_df, users_df):
    print("[gmv_by_segment] building...")
    orders_df = orders_df.copy()
    orders_df["category"] = orders_df["category_mix"].apply(
        lambda s: list(__import__("json").loads(s).keys())[0]
    )
    merged = orders_df.merge(
        users_df[["user_id","city_tier","device_type"]], on="user_id", how="left"
    )
    agg = (
        merged.groupby(["city_tier","device_type","payment_method","category"])
        .agg(
            total_orders    =("order_id","count"),
            avg_gmv         =("gmv","mean"),
            total_gmv       =("gmv","sum"),
            return_rate_pct =("return_initiated","mean"),
        )
        .reset_index()
    )
    agg["avg_gmv"]         = agg["avg_gmv"].round(2)
    agg["total_gmv"]       = agg["total_gmv"].round(2)
    agg["return_rate_pct"] = (agg["return_rate_pct"] * 100).round(2)
    agg["gold_loaded_at"]  = RUN_TS
    return agg


# ------------------------------------------------------------------------------
# main
# ------------------------------------------------------------------------------
def run():
    print("=" * 55)
    print("GOLD LAYER LOAD")
    print("=" * 55)

    # read silver
    print("\n[silver] reading tables...")
    s_conn = get_conn(database=SILVER_DB)
    users_df  = read_silver(s_conn, "users")
    orders_df = read_silver(s_conn, "orders")
    events_df = read_silver(s_conn, "events",
                            "user_id,session_id,event_name,event_timestamp,event_date,price_band")
    s_conn.close()
    print(f"  users: {len(users_df):,} | events: {len(events_df):,} | orders: {len(orders_df):,}")

    # build gold tables
    funnel_df    = build_funnel_summary(events_df)
    segment_df   = build_segment_dropoff(events_df, users_df)
    cohort_df    = build_cohort_retention(users_df, orders_df)
    ttc_df       = build_time_to_convert(events_df, orders_df)
    gmv_df       = build_gmv_by_segment(orders_df, users_df)

    # write to gold_db
    print("\n[gold_db] writing tables...")
    g_conn_root = get_conn()
    cur = g_conn_root.cursor()
    cur.execute(f"CREATE DATABASE IF NOT EXISTS `{GOLD_DB}`")
    g_conn_root.commit()
    cur.close()
    g_conn_root.close()

    g_conn = get_conn(database=GOLD_DB)
    cur    = g_conn.cursor()
    for name, df in [
        ("funnel_summary",   funnel_df),
        ("segment_dropoff",  segment_df),
        ("cohort_retention", cohort_df),
        ("time_to_convert",  ttc_df),
        ("gmv_by_segment",   gmv_df),
    ]:
        write_table(cur, g_conn, name, df)
    cur.close()
    g_conn.close()

    print("\n" + "=" * 55)
    print("Gold load complete.")
    print(f"Database : {GOLD_DB}")
    print(f"Tables   : funnel_summary, segment_dropoff, cohort_retention,")
    print(f"           time_to_convert, gmv_by_segment")
    print(f"Loaded at: {RUN_TS}")
    print("=" * 55)


if __name__ == "__main__":
    run()
