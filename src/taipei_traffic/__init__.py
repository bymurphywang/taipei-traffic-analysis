"""臺北市113年（2024）A1及A2類交通事故分析套件。

模組結構：
- codes:    肇因碼／車種／天候等代碼對照表（112.7.1 後適用版本）
- data:     原始 CSV 載入與清理（Big5 編碼、民國年、衍生欄位）
- db:       建置 SQLite 資料庫（accidents / parties / 代碼維度表）
- stats:    以 SQL 產生統計表（輸出至 分析結果/統計表/）
- charts:   產生補充圖表
- models:   統計檢定與事故嚴重度模型
- pipeline: 一鍵重跑整條分析流程
"""

__version__ = "1.0.0"
