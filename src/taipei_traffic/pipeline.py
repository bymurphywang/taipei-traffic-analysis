"""一鍵重跑分析流程：

    uv run python -m taipei_traffic.pipeline              # 全部步驟
    uv run python -m taipei_traffic.pipeline --steps db,stats

步驟：
    db      原始 CSV → SQLite（data/traffic.sqlite）
    stats   SQL 統計 → 分析結果/統計表/*.csv
    charts  補充圖表 → 分析結果/圖表/
    models  統計檢定與嚴重度模型 → 分析結果/模型結果/
"""

import argparse

from .config import DB_PATH, RAW_CSV

ALL_STEPS = ["db", "stats", "charts", "models"]


def main() -> None:
    parser = argparse.ArgumentParser(description="臺北市交通事故分析 pipeline")
    parser.add_argument(
        "--steps",
        default=",".join(ALL_STEPS),
        help=f"要執行的步驟（逗號分隔）：{','.join(ALL_STEPS)}",
    )
    args = parser.parse_args()
    steps = [s.strip() for s in args.steps.split(",") if s.strip()]

    unknown = set(steps) - set(ALL_STEPS)
    if unknown:
        parser.error(f"未知步驟：{unknown}")

    if "db" in steps:
        print("【1/4】建置 SQLite 資料庫...")
        if not RAW_CSV.exists():
            raise SystemExit(
                f"找不到原始資料 {RAW_CSV.name}，"
                "請自 https://data.gov.tw/dataset/130110 下載後放到專案根目錄"
            )
        from .db import build_db

        build_db()
        print(f"✓ 資料庫已建置：{DB_PATH}")

    if "stats" in steps:
        print("【2/4】產生統計表...")
        from .stats import generate_all as generate_stats

        generate_stats()

    if "charts" in steps:
        print("【3/4】產生補充圖表...")
        from .charts import generate_all as generate_charts

        generate_charts()

    if "models" in steps:
        print("【4/4】統計檢定與嚴重度模型...")
        from .models import run_all as run_models

        run_models()

    print("\n分析流程完成 ✓")


if __name__ == "__main__":
    main()
