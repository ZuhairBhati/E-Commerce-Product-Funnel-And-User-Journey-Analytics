# config.py — central credentials and path config
DB_CONFIG = {
    "host":     "localhost",
    "user":     "root",
    "password": "root123",
    "port":     3306,
}

BRONZE_DB = "bronze_db"
SILVER_DB = "silver_db"
GOLD_DB   = "gold_db"

BRONZE_DIR = "./data/bronze"
GOLD_EXPORT_DIR = "./data/gold_exports"
