"""補充圖表：月份 × 雨天事故雙軸圖。

探索性圖表（01-11）由 完整分析.ipynb 產生；本模組負責 pipeline 新增的圖表。
"""

import platform
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from .config import CHART_DIR, DB_PATH
from .db import connect
from .stats import run_query


def setup_fonts() -> None:
    system = platform.system()
    if system == "Darwin":
        plt.rcParams["font.sans-serif"] = ["Arial Unicode MS", "PingFang TC", "Heiti TC"]
    elif system == "Windows":
        plt.rcParams["font.sans-serif"] = ["Microsoft JhengHei", "Taipei Sans TC Beta"]
    else:
        plt.rcParams["font.sans-serif"] = ["Noto Sans CJK TC", "WenQuanYi Micro Hei"]
    plt.rcParams["axes.unicode_minus"] = False


def monthly_weather_chart(db_path: Path = DB_PATH, out_dir: Path = CHART_DIR) -> Path:
    """繪製各月份總事故（長條）與雨天事故（折線，右軸）雙軸圖。"""
    setup_fonts()
    out_dir.mkdir(parents=True, exist_ok=True)

    with connect(db_path) as conn:
        df = run_query(conn, "weather_monthly.sql")

    fig, ax_total = plt.subplots(figsize=(14, 7))

    ax_total.bar(df["發生月"], df["事故件數"], color="#d3d3d3", label="總事故件數")
    ax_total.set_xlabel("月份", fontsize=12)
    ax_total.set_ylabel("總事故件數", fontsize=12)
    ax_total.set_xticks(df["發生月"])
    ax_total.set_xticklabels([f"{m}月" for m in df["發生月"]])

    ax_rain = ax_total.twinx()
    ax_rain.plot(
        df["發生月"], df["雨天事故件數"],
        color="#1f77b4", marker="o", linewidth=2.5, label="雨天事故件數",
    )
    ax_rain.set_ylabel("雨天事故件數", fontsize=12, color="#1f77b4")
    ax_rain.tick_params(axis="y", labelcolor="#1f77b4")

    for _, row in df.iterrows():
        ax_rain.annotate(
            f"{row['雨天佔比(%)']:.0f}%",
            (row["發生月"], row["雨天事故件數"]),
            textcoords="offset points", xytext=(0, 10),
            ha="center", fontsize=9, color="#1f77b4",
        )

    ax_total.set_title(
        "113年臺北市各月份事故件數與雨天事故關聯", fontsize=15, fontweight="bold", pad=15
    )
    lines1, labels1 = ax_total.get_legend_handles_labels()
    lines2, labels2 = ax_rain.get_legend_handles_labels()
    ax_total.legend(lines1 + lines2, labels1 + labels2, loc="upper right")

    out_path = out_dir / "12_月份天氣分析.png"
    fig.tight_layout()
    fig.savefig(out_path, dpi=150)
    plt.close(fig)
    print(f"✓ {out_path.name}")
    return out_path


def generate_all(db_path: Path = DB_PATH, out_dir: Path = CHART_DIR) -> list[Path]:
    return [monthly_weather_chart(db_path, out_dir)]
