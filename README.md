---
title: Taipei Traffic Analysis
emoji: 🚦
colorFrom: blue
colorTo: indigo
sdk: gradio
sdk_version: "6.20.0"
python_version: "3.11"
app_file: app/gradio_app.py
pinned: false
---

# 臺北市 113 年（2024）A1/A2 類交通事故多維度分析

> **Taipei City 2024 Traffic Accident Analysis** — an end-to-end data product:
> reproducible pipeline (CSV → SQLite → SQL stats), statistical inference,
> an interactive Streamlit dashboard with GPS hotspot mapping, and a FastAPI
> statistics service. *(English overview [below](#english-overview).)*

分析臺北市 113 年全年 **51,810 筆當事人紀錄／22,368 件 A1、A2 類交通事故**
（政府開放資料），從探索性分析出發，完成資料工程、推論統計、互動視覺化與
API 服務的完整交付。統計口徑經與官方《臺北市 113 年交通事故分析報告》逐項驗證。

## 主要發現

- **時空集中**：事故高峰為上午 8 時與 17–18 時通勤時段；中山、大安、中正、信義、內湖前 5 區佔全市 52.6%
- **肇因**：前 10 大肇因全為人為因素，「恍神／分心駕駛」（9.6%）居首；「右轉彎未依規定」中小客車涉入達 53.1%，反映轉彎車與直行機車的路權衝突
- **嚴重度（邏輯迴歸）**：控制其他因素後，**大型車 OR 6.7、清晨時段 OR 2.7、速限每 +10km/h OR 1.3** 顯著推升死亡風險；雨天推升事故「數量」（颱風季 10 月雨天事故佔比 29.4%）但與「嚴重度」無顯著關聯（χ² p=0.43）

完整結果見 **[完整研究報告.md](完整研究報告.md)**。

## 系統架構

```
原始 CSV（Big5, 51,810 筆當事人）
        │  src/taipei_traffic/data.py   清理：民國年→西元、事故ID重建、異常值
        ▼
SQLite（accidents / parties / 代碼維度表）── src/taipei_traffic/db.py
        │
        ├── sql/*.sql（10 支查詢，窗函數）──► 分析結果/統計表/*.csv
        ├── src/taipei_traffic/models.py ──► 卡方檢定＋邏輯迴歸（分析結果/模型結果/）
        ├── src/taipei_traffic/figures.py ─► 共用 Plotly 圖表模組
        │       ├── app/dashboard.py   ──► Streamlit 儀表板（本機，pydeck 地圖）
        │       └── app/gradio_app.py  ──► Gradio 儀表板（線上 demo，HF Spaces）
        └── api/main.py       ──► FastAPI REST 服務（/docs Swagger）
```

統計表、儀表板與 API 讀取**同一個資料庫、同一套 SQL**，數字單一口徑。

## 快速開始

需求：[uv](https://docs.astral.sh/uv/)（Python 3.11 自動安裝）

```bash
git clone <repo-url> && cd taipei-traffic-analysis
uv sync

# 1) 重跑完整分析（需原始 CSV，見下方資料來源；已附建好的 SQLite 可跳過）
uv run python -m taipei_traffic.pipeline

# 2) 互動儀表板（Streamlit 版；或 Gradio 版：uv run python app/gradio_app.py）
uv run streamlit run app/dashboard.py

# 3) REST API（Swagger 文件在 http://127.0.0.1:8000/docs）
uv run uvicorn api.main:app
```

倉庫已附建置完成的 `data/traffic.sqlite`，儀表板與 API 可直接啟動；
只有重跑 `pipeline` 的 `db` 步驟才需要原始 CSV。

### 資料來源

| 檔案 | 來源 |
|------|------|
| 113年-臺北市A1及A2類交通事故明細.csv | [政府資料開放平台 data.gov.tw/dataset/130110](https://data.gov.tw/dataset/130110)（下載後置於專案根目錄）|
| 代碼對照 | 道路交通事故調查報告表（112.7.1 後適用版本），已整理為 `src/taipei_traffic/codes.py` |

## 專案結構

```
├── src/taipei_traffic/     # 分析套件：資料清理、SQLite、SQL 統計、共用圖表、統計模型、pipeline
├── sql/                    # 10 支統計查詢（佔比/累積佔比用窗函數）
├── app/dashboard.py        # Streamlit 儀表板（本機）
├── app/gradio_app.py       # Gradio 儀表板（線上 demo）
├── api/main.py             # FastAPI 服務
├── 完整分析.ipynb          # 探索性分析（圖表 01–11 由此產生）
├── 完整研究報告.md         # 研究報告（方法、結果、政策建議）
└── 分析結果/               # 統計表（CSV）、圖表（PNG）、模型結果
```

## 部署（Hugging Face Spaces）

本 README 開頭的 YAML 即 Space 設定（Gradio SDK）。二進位檔（SQLite/PNG）以 Git LFS 追蹤。

1. 在 [huggingface.co/new-space](https://huggingface.co/new-space) 建立 Space：SDK 選 **Gradio**（Blank）、硬體 **ZeroGPU**（2026 年起免費帳號僅此選項；本 app 純 CPU 運算，不會動用 GPU 配額）
2. 推送：
   ```bash
   git remote add hf https://huggingface.co/spaces/<帳號>/taipei-traffic-analysis
   git lfs push --all hf main && git push -f hf main
   ```

## 技術棧

Python 3.11 · uv · pandas · SQLite/SQL · SciPy · statsmodels · Plotly · Streamlit · Gradio · pydeck · FastAPI · Matplotlib/Seaborn · Git LFS

## 統計方法備註

- 事故件數以「當事人序號 = 1」重建（原始資料一列一位當事人），與官方口徑一致
- 肇因統計僅計第一當事人；A1/A2、死傷人數與官方報告逐項核對相符
- 死亡事故為罕見事件（72/22,368），邏輯迴歸用於解讀風險因子方向與相對強度（勝算比＋95% CI），非機率預測器
- 卡方檢定附 Cramér's V 效果量

---

## English Overview

**What**: End-to-end analysis of all 22,368 injury/fatality traffic accidents
(51,810 party records) in Taipei City, 2024, from Taiwan's open-data platform.

**Highlights**

- **Data engineering**: Big5-encoded raw CSV → cleaned SQLite star-ish schema
  (accidents / parties / code dimension tables); all statistics generated from
  SQL (window functions), one command to reproduce: `uv run python -m taipei_traffic.pipeline`
- **Statistical inference**: chi-square independence tests and a logistic
  regression on fatality — heavy vehicles (OR 6.7), pre-dawn hours (OR 2.7),
  and higher speed limits (OR 1.3 per +10 km/h) significantly raise fatality
  odds, while rain raises accident *counts* but not *severity*
- **Interactive dashboard** (Streamlit + Plotly + pydeck): GPS density heatmap
  with fatal-accident markers, cross-filterable time/cause/vehicle views,
  odds-ratio forest plot; colorblind-validated palette
- **REST API** (FastAPI): summary, ten statistical tables, and filtered
  accident queries sharing the exact SQL used for the published tables
- Figures validated line-by-line against the official Taipei City 2024
  traffic accident report

**Run it**: `uv sync`, then `uv run streamlit run app/dashboard.py`
(a pre-built SQLite database ships with the repo).
