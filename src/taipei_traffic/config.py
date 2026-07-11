"""專案路徑設定。所有模組共用，避免路徑散落各處。"""

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

RAW_CSV = PROJECT_ROOT / "113年-臺北市A1及A2類交通事故明細.csv"
DB_PATH = PROJECT_ROOT / "data" / "traffic.sqlite"
SQL_DIR = PROJECT_ROOT / "sql"

RESULT_DIR = PROJECT_ROOT / "分析結果"
TABLE_DIR = RESULT_DIR / "統計表"
CHART_DIR = RESULT_DIR / "圖表"
MODEL_DIR = RESULT_DIR / "模型結果"
