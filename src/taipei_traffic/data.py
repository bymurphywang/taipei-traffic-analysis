"""原始資料載入與清理。

原始 CSV 為 Big5 編碼的「當事人」明細（一列一位當事人），
同一起事故的當事人為連續列、以 當事人序號=1 起頭；
因此以 (當事人序號==1).cumsum() 重建事故 ID。
"""

from pathlib import Path

import pandas as pd

from .codes import TIME_PERIODS, vehicle_category
from .config import RAW_CSV

# 速限欄位存在極端異常值（如 502），臺北市市區道路速限上限以 110 作合理界線
MAX_REASONABLE_SPEED_LIMIT = 110


def load_raw(csv_path: Path = RAW_CSV) -> pd.DataFrame:
    """讀取原始 CSV（Big5，失敗時退回 cp950）。"""
    try:
        return pd.read_csv(csv_path, encoding="big5")
    except UnicodeDecodeError:
        return pd.read_csv(csv_path, encoding="cp950")


def classify_time_period(hour: int) -> str:
    if 0 <= hour <= 5:
        return TIME_PERIODS[0]
    if 6 <= hour <= 11:
        return TIME_PERIODS[1]
    if 12 <= hour <= 17:
        return TIME_PERIODS[2]
    return TIME_PERIODS[3]


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """清理當事人明細並加入衍生欄位（事故ID、西元日期、星期、時段等）。"""
    df = df.copy()

    df["accident_id"] = (df["當事人序號"] == 1).cumsum()

    df["西元年"] = df["發生年度"] + 1911
    df["日期"] = pd.to_datetime(
        df[["西元年", "發生月", "發生日"]].rename(
            columns={"西元年": "year", "發生月": "month", "發生日": "day"}
        )
    )
    df["星期數"] = df["日期"].dt.dayofweek  # 0=星期一
    df["時段"] = df["發生時-Hours"].apply(classify_time_period)

    # 年齡以 -1 標記缺失
    df.loc[df["年齡"] < 0, "年齡"] = pd.NA

    df.loc[df["速限-速度限制"] > MAX_REASONABLE_SPEED_LIMIT, "速限-速度限制"] = pd.NA

    df["車種大類"] = df["車種"].map(vehicle_category)
    df["是否雨天"] = (df["天候"] == 6).astype(int)

    return df


def load_clean(csv_path: Path = RAW_CSV) -> pd.DataFrame:
    return clean(load_raw(csv_path))
