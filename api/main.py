"""臺北市113年（2024）交通事故統計 REST API。

啟動方式：
    uv run uvicorn api.main:app --reload

互動式文件（Swagger UI）： http://127.0.0.1:8000/docs
統計端點重用 sql/ 目錄的查詢，與統計表輸出完全同一套口徑。
"""

import sqlite3
from typing import Annotated

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel

from taipei_traffic.config import DB_PATH
from taipei_traffic.stats import QUERY_OUTPUTS, run_query

app = FastAPI(
    title="臺北市113年交通事故統計 API",
    description=(
        "提供臺北市 113 年（2024）A1/A2 類交通事故的彙總統計與明細查詢。"
        "資料來源：政府資料開放平台（data.gov.tw/dataset/130110）。"
    ),
    version="1.0.0",
)

# 端點名稱 → SQL 查詢檔
_STATS_QUERIES = {
    "monthly": "monthly_stats.sql",
    "hourly": "hourly_stats.sql",
    "time-periods": "time_period_stats.sql",
    "districts": "district_stats.sql",
    "causes": "cause_stats.sql",
    "vehicles": "vehicle_stats.sql",
    "cause-vehicle-cross": "cause_vehicle_cross.sql",
    "gender": "gender_stats.sql",
    "age": "age_stats.sql",
    "weather": "weather_monthly.sql",
}


class Summary(BaseModel):
    total_accidents: int
    a1_accidents: int
    a2_accidents: int
    deaths_24h: int
    deaths_2_30d: int
    injuries: int


def _connect() -> sqlite3.Connection:
    if not DB_PATH.exists():
        raise HTTPException(
            status_code=503,
            detail="資料庫尚未建置，請先執行 python -m taipei_traffic.pipeline --steps db",
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


@app.get("/health", tags=["system"])
def health() -> dict:
    return {"status": "ok", "database": DB_PATH.exists()}


@app.get("/summary", response_model=Summary, tags=["stats"])
def summary() -> Summary:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT COUNT(*)                                   AS total_accidents,
                   SUM(severity = 'A1')                       AS a1_accidents,
                   SUM(severity = 'A2')                       AS a2_accidents,
                   SUM(deaths_24h)                            AS deaths_24h,
                   SUM(deaths_2_30d)                          AS deaths_2_30d,
                   SUM(injuries)                              AS injuries
            FROM accidents
            """
        ).fetchone()
    return Summary(**dict(row))


@app.get("/stats/{name}", tags=["stats"])
def stats(name: str) -> list[dict]:
    """回傳指定統計表，欄位與 分析結果/統計表/ 的 CSV 一致。

    可用名稱：monthly, hourly, time-periods, districts, causes, vehicles,
    cause-vehicle-cross, gender, age, weather
    """
    sql_name = _STATS_QUERIES.get(name)
    if sql_name is None:
        raise HTTPException(
            status_code=404,
            detail=f"未知統計表 '{name}'，可用：{', '.join(_STATS_QUERIES)}",
        )
    with _connect() as conn:
        df = run_query(conn, sql_name)
    return df.to_dict(orient="records")


@app.get("/accidents", tags=["accidents"])
def accidents(
    month: Annotated[int | None, Query(ge=1, le=12, description="發生月")] = None,
    district: Annotated[str | None, Query(description="行政區，如 03中山區")] = None,
    severity: Annotated[str | None, Query(pattern="^A[12]$", description="A1 或 A2")] = None,
    hour: Annotated[int | None, Query(ge=0, le=23, description="發生時")] = None,
    limit: Annotated[int, Query(ge=1, le=1000)] = 100,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> dict:
    """依條件查詢事故明細（事故層級，一列一起事故）。"""
    where, params = [], []
    if month is not None:
        where.append("month = ?")
        params.append(month)
    if district is not None:
        where.append("district = ?")
        params.append(district)
    if severity is not None:
        where.append("severity = ?")
        params.append(severity)
    if hour is not None:
        where.append("hour = ?")
        params.append(hour)
    where_sql = f"WHERE {' AND '.join(where)}" if where else ""

    with _connect() as conn:
        total = conn.execute(
            f"SELECT COUNT(*) FROM accidents {where_sql}", params
        ).fetchone()[0]
        rows = conn.execute(
            f"""
            SELECT accident_id, date, hour, minute, district, location, severity,
                   deaths_24h, deaths_2_30d, injuries, weather_code, cause_code,
                   first_vehicle_code, lon, lat
            FROM accidents {where_sql}
            ORDER BY date, hour, minute
            LIMIT ? OFFSET ?
            """,
            [*params, limit, offset],
        ).fetchall()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": [dict(r) for r in rows],
    }
