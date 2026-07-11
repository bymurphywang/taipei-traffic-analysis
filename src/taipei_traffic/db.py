"""建置 SQLite 資料庫。

資料表設計（欄位使用英文 snake_case，值保留中文標籤）：
- accidents      事故層級（一列一起事故，取第一當事人衍生）
- parties        當事人層級（一列一位當事人）
- cause_codes    肇因碼維度表
- vehicle_codes  車種代碼維度表
"""

import sqlite3
from pathlib import Path

import pandas as pd

from .codes import CAUSE_MAP, VEHICLE_MAP, WEEKDAY_MAP, vehicle_category
from .config import DB_PATH, RAW_CSV
from .data import load_clean

_PARTY_COLUMNS = {
    "accident_id": "accident_id",
    "當事人序號": "party_seq",
    "車種": "vehicle_code",
    "車種大類": "vehicle_category",
    "性別": "gender_code",
    "年齡": "age",
    "受傷程度": "injury_code",
    "肇因碼-個別": "cause_code_individual",
    "肇因碼-主要": "cause_code_main",
    "飲酒情形": "drinking_code",
    "駕駛資格情形": "license_code",
    "個人肇逃否": "hit_and_run_code",
}

_ACCIDENT_COLUMNS = {
    "accident_id": "accident_id",
    "西元年": "year",
    "發生月": "month",
    "發生日": "day",
    "發生時-Hours": "hour",
    "發生分": "minute",
    "星期數": "weekday",
    "時段": "time_period",
    "區序": "district",
    "肇事地點": "location",
    "死亡人數": "deaths_24h",
    "2-30日死亡人數": "deaths_2_30d",
    "受傷人數": "injuries",
    "天候": "weather_code",
    "是否雨天": "is_rain",
    "速限-速度限制": "speed_limit",
    "肇因碼-個別": "cause_code",
    "車種": "first_vehicle_code",
    "座標-X": "lon",
    "座標-Y": "lat",
}

_INDEXES = [
    "CREATE INDEX idx_accidents_month ON accidents(month)",
    "CREATE INDEX idx_accidents_district ON accidents(district)",
    "CREATE INDEX idx_accidents_cause ON accidents(cause_code)",
    "CREATE INDEX idx_accidents_severity ON accidents(severity)",
    "CREATE INDEX idx_parties_accident ON parties(accident_id)",
    "CREATE INDEX idx_parties_vehicle ON parties(vehicle_code)",
    "CREATE INDEX idx_parties_cause ON parties(cause_code_individual)",
]


def build_db(csv_path: Path = RAW_CSV, db_path: Path = DB_PATH) -> Path:
    """從原始 CSV 建置 SQLite 資料庫，回傳資料庫路徑。"""
    df = load_clean(csv_path)

    # 含 NaN 的代碼欄在 pandas 預設為 float，改用可空整數避免寫入 108.0 這類值
    for col in [
        "性別", "受傷程度", "肇因碼-個別", "肇因碼-主要",
        "飲酒情形", "駕駛資格情形", "個人肇逃否", "速限-速度限制", "年齡",
    ]:
        df[col] = df[col].astype("Int64")

    parties = df[list(_PARTY_COLUMNS)].rename(columns=_PARTY_COLUMNS)

    first = df[df["當事人序號"] == 1]
    accidents = first[list(_ACCIDENT_COLUMNS)].rename(columns=_ACCIDENT_COLUMNS)
    accidents = accidents.assign(
        severity=first["處理別-編號"].map({1: "A1", 2: "A2"}).values,
        date=first["日期"].dt.strftime("%Y-%m-%d").values,
        weekday_name=first["星期數"].map(WEEKDAY_MAP).values,
        is_fatal=((first["死亡人數"] + first["2-30日死亡人數"]) > 0).astype(int).values,
    )

    cause_codes = pd.DataFrame(
        [{"code": k, "label": v} for k, v in CAUSE_MAP.items()]
    )
    vehicle_codes = pd.DataFrame(
        [
            {"code": k, "label": v, "category": vehicle_category(k)}
            for k, v in VEHICLE_MAP.items()
        ]
    )

    db_path.parent.mkdir(parents=True, exist_ok=True)
    db_path.unlink(missing_ok=True)

    with sqlite3.connect(db_path) as conn:
        accidents.to_sql("accidents", conn, index=False)
        parties.to_sql("parties", conn, index=False)
        cause_codes.to_sql("cause_codes", conn, index=False)
        vehicle_codes.to_sql("vehicle_codes", conn, index=False)
        for stmt in _INDEXES:
            conn.execute(stmt)

    return db_path


def connect(db_path: Path = DB_PATH) -> sqlite3.Connection:
    if not db_path.exists():
        raise FileNotFoundError(
            f"找不到資料庫 {db_path}，請先執行 python -m taipei_traffic.pipeline --steps db"
        )
    return sqlite3.connect(db_path)
