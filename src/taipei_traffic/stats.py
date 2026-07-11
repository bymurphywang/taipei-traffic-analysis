"""以 SQL 產生統計表，輸出至 分析結果/統計表/。

每張統計表對應 sql/ 目錄下的一支查詢，性別統計另以代碼表補上中文標籤。
"""

import sqlite3
from pathlib import Path

import pandas as pd

from .codes import GENDER_MAP
from .config import DB_PATH, SQL_DIR, TABLE_DIR
from .db import connect

# SQL 檔名 → 輸出統計表檔名
QUERY_OUTPUTS = {
    "monthly_stats.sql": "月份統計.csv",
    "time_period_stats.sql": "時段統計.csv",
    "hourly_stats.sql": "每小時統計.csv",
    "district_stats.sql": "行政區統計.csv",
    "cause_stats.sql": "肇因統計.csv",
    "vehicle_stats.sql": "車種統計.csv",
    "cause_vehicle_cross.sql": "肇因車種交叉統計.csv",
    "gender_stats.sql": "性別統計.csv",
    "age_stats.sql": "年齡統計.csv",
    "weather_monthly.sql": "天氣月份統計.csv",
}


def run_query(conn: sqlite3.Connection, sql_name: str) -> pd.DataFrame:
    sql = (SQL_DIR / sql_name).read_text(encoding="utf-8")
    return pd.read_sql_query(sql, conn)


def generate_all(db_path: Path = DB_PATH, out_dir: Path = TABLE_DIR) -> list[Path]:
    """執行全部統計查詢並輸出 CSV，回傳輸出檔案清單。"""
    out_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    with connect(db_path) as conn:
        for sql_name, csv_name in QUERY_OUTPUTS.items():
            df = run_query(conn, sql_name)

            if sql_name == "gender_stats.sql":
                df.insert(1, "性別", df["性別代碼"].map(GENDER_MAP))

            out_path = out_dir / csv_name
            df.to_csv(out_path, index=False, encoding="utf-8-sig")
            written.append(out_path)
            print(f"✓ {csv_name}（{len(df)} 列）")

    return written
