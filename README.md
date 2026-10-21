<div align="center">

# 🛍️ E-Commerce Product Funnel & User Journey Analytics

A portfolio-grade end-to-end data engineering and analytics project simulating a **multi-category e-commerce platform** (Fashion, Beauty, Electronics).

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![MySQL](https://img.shields.io/badge/MySQL-8.0-4479A1?style=for-the-badge&logo=mysql&logoColor=white)](https://mysql.com)
[![Power BI](https://img.shields.io/badge/Power_BI-Dashboard-4285F4?style=for-the-badge&logo=looker&logoColor=white)](https://lookerstudio.google.com)
[![Jupyter](https://img.shields.io/badge/Jupyter-Notebooks-F37626?style=for-the-badge&logo=jupyter&logoColor=white)](https://jupyter.org)


</div>

---

## 📌 Overview

This project simulates a production-grade analytics pipeline for E-commerce platforms like (Amazon, Flipkart, Myntra, Nykaa, Meesho), covering:

- **Synthetic data generation** at scale (150K users, 3M events, ~38K orders)
- **ETL pipeline** implementing the Medallion Architecture (Bronze → Silver → Gold)
- **Exploratory Data Analysis** with 11 analytical sections
- **A/B Testing** with 3 statistical hypothesis tests
- **Power BI Dashboard** with 3 report pages and a star schema data model
- **7 Analytical SQL queries** including a session-level funnel view

---

## 📁 Project Structure

```
ecommerce-funnel-analytics/
│
├── data/
│   ├── bronze/                  # Raw Parquet files (landing zone)
│   │   ├── users.parquet
│   │   ├── events.parquet
│   │   └── orders.parquet
│   │
│   └── gold_exports/            # EDA chart exports (PNG)
│
├── etl/
│   ├── config.py                # DB credentials and path config
│   ├── generate.py              # Synthetic data generation
│   ├── bronze.py                # Raw data → bronze_db (MySQL)
│   ├── silver.py                # bronze_db → silver_db (cleaned + typed)
│   └── gold.py                  # silver_db → gold_db (aggregated marts)
│
├── sql/
│   ├── 01_funnel_conversion_by_tier.sql
│   ├── 02_channel_gmv_ranking.sql
│   ├── 03_coupon_vs_noncoupon_revenue.sql
│   ├── 04_device_tier_dropoff.sql
│   ├── 05_weekly_gmv_trend.sql
│   ├── 06_payment_method_return_rate.sql
│   └── 07_vw_funnel_steps.sql   # Session-level funnel view (base for all queries)
│
├── notebooks/
│   ├── eda.ipynb                # 11-section EDA with charts
│   └── ab_testing.ipynb         # 3 statistical A/B tests
│
├── powerbi/
│   └── myntra_dashboard.pbix    # 3-page Power BI report
│
└── README.md
```

---

## 🛠️ Tech Stack

| Layer | Tools |
|---|---|
| Data Generation | Python, Faker, NumPy, pandas |
| ETL Pipeline | Python, MySQL (bronze / silver / gold DBs) |
| Data Quality | Custom DQ log in silver layer |
| Analysis | Python, SciPy, Matplotlib, Seaborn |
| SQL Analytics | MySQL, analytical SQL (window functions, CTEs, views) |
| Visualisation | Power BI Desktop (MySQL connector) |
| Version Control | Git / GitHub |

---

## 🏗️ Project Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        DATA GENERATION                          │
│  generate.py → users.parquet + events.parquet + orders.parquet  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│                      MEDALLION PIPELINE                         │
│                                                                 │
│  bronze.py        silver.py              gold.py               │
│  Raw landing  →   Cleaned + typed   →    Aggregated marts      │
│  (bronze_db)      (silver_db)            (gold_db)             │
└────────────────────────────┬────────────────────────────────────┘
                             │
                  ┌──────────┴──────────┐
                  ▼                     ▼
        ┌─────────────────┐   ┌──────────────────────┐
        │   SQL Queries   │   │    Power BI Report   │
        │  (7 .sql files) │   │  (3 dashboard pages) │
        └─────────────────┘   └──────────────────────┘
                  │
                  ▼
        ┌─────────────────┐
        │    Notebooks    │
        │  EDA + A/B Test │
        └─────────────────┘
```

---

## 🏅 Medallion Pipeline

### Bronze Layer (`bronze_db`)
- Raw Parquet files loaded **as-is** into MySQL
- Adds `ingested_at` metadata timestamp
- Full refresh on each run — acts as the raw landing zone

### Silver Layer (`silver_db`)
- Reads from bronze, applies **data quality checks** (logged to `data_quality_log` table):
  - Null checks on critical columns
  - Duplicate PK detection + deduplication
  - Orphan FK validation
  - Invalid enum value detection
- Applies **transformations**:
  - Standardises categoricals to lowercase
  - Derives `event_date` from `event_timestamp`
  - Derives `gmv_band` (low / mid / high / premium) via `pd.cut`
  - Adds `is_returner` flag on users from orders
- Adds `silver_loaded_at` audit timestamp

### Gold Layer (`gold_db`)
Builds **5 analytical mart tables** from silver:

| Table | Description |
|---|---|
| `funnel_summary` | Step-over-step conversion & drop-off rates |
| `segment_dropoff` | Category → PDP conversion by device, channel, city tier, age band, price band |
| `cohort_retention` | Weekly signup cohorts tracked by order activity |
| `time_to_convert` | Days + sessions from first app_open to first order, by category |
| `gmv_by_segment` | Avg/total GMV + return rate by tier × device × payment × category |

---

## 📊 Key Findings & Insights

### Funnel Analysis
- **Category → PDP is the biggest leak** (60% drop-off) — the primary optimisation opportunity
- Desktop users have the **worst drop-off** (41.4%); Android worst among mobile devices

### Revenue & GMV
- **Coupon orders have significantly higher GMV** (₹2,919 vs ₹2,614 — p < 0.001, t-test)
- Electronics drives the **highest average order value**; Fashion has the **highest return rate** (~25%)

### Device & Platform
- **Android conversion is statistically higher than iOS** (23.5% vs 22.0% — p < 0.001, chi-square)
- Mobile accounts for 80%+ of sessions (Android 58%, iOS 22%)

### Returns & Payments
- **COD has a materially higher return rate** than prepaid methods — operational cost implication
- **Tier-2 return rate is significantly higher than Tier-1** (18.5% vs 17.5% — p = 0.04, chi-square)

### Acquisition
- **Organic Search + Instagram together drive 58% of users** — aligned with Myntra's real acquisition mix

---

## 🔬 A/B Tests

| Test | Method | Result |
|---|---|---|
| Coupon vs Non-Coupon GMV | Independent t-test | ✅ Significant — coupon users spend more (₹2,919 vs ₹2,614) |
| iOS vs Android Conversion | Chi-square | ✅ Significant — Android converts higher (23.5% vs 22.0%) |
| Tier-1 vs Tier-2 Return Rate | Chi-square | ✅ Significant — Tier-2 returns more (18.5% vs 17.5%) |

---

## 📈 Dashboard Pages

| Page | Source Tables | Key Visuals |
|---|---|---|
| Funnel Overview | `funnel_summary` | Conversion bar chart, 3 KPI cards |
| Segment Drop-off | `segment_dropoff` | Drop-off & conversion by dimension (device / tier / channel / age / price) |
| Retention & Time to Convert | `cohort_retention`, `time_to_convert` | Weekly cohort heatmap, days-to-convert distribution |

**Data Model:** Star schema with `Category Bridge` dimension table connecting `gmv_by_segment` and `time_to_convert`. `segment_dropoff` connected via Many-to-Many on `city_tier`.

---

## 🚀 How to Run

### Prerequisites
- Python 3.9+
- MySQL 8.0+
- Power BI Desktop (Windows)

### 1. Install dependencies
```bash
pip install pandas numpy faker mysql-connector-python scipy matplotlib seaborn pyarrow
```

### 2. Configure credentials
Edit `etl/config.py`:
```python
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "your_password",
    "port": 3306,
}
```

### 3. Generate synthetic data
```bash
python etl/generate.py
```
> ⏱️ ~45–60 seconds at full scale. Outputs Parquet files to `data/bronze/`

### 4. Run the ETL pipeline in order
```bash
python etl/bronze.py
python etl/silver.py
python etl/gold.py
```

### 5. Run SQL analytics
Connect any MySQL client to `silver_db` / `gold_db`.
> Start with `sql/07_vw_funnel_steps.sql` — creates the session-level funnel view used by all other queries.

### 6. Run notebooks
```bash
cd notebooks && jupyter notebook
```
- `eda.ipynb` — 11-section exploratory analysis
- `ab_testing.ipynb` — 3 statistical hypothesis tests

### 7. Open Power BI Dashboard
Open `powerbi/myntra_dashboard.pbix` → connect to `gold_db` via MySQL connector → Refresh.

---

*Built as a portfolio project targeting Senior Data Analyst / Product Analyst roles at Myntra, Nykaa, Zepto, CRED, Razorpay.*
