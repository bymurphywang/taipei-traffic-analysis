"""臺北市113年（2024）交通事故互動式分析儀表板（Streamlit 版，本機使用）。

啟動方式：
    uv run streamlit run app/dashboard.py

需先建置資料庫：
    uv run python -m taipei_traffic.pipeline --steps db,models

圖表邏輯集中在 taipei_traffic.figures，與線上 Gradio 版（app/gradio_app.py）共用。
"""

import sys
from pathlib import Path

# 部署環境可能只安裝相依套件、不安裝本專案本身，直接把 src/ 加入匯入路徑
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import pydeck as pdk
import streamlit as st

from taipei_traffic.codes import TIME_PERIODS
from taipei_traffic.config import DB_PATH, MODEL_DIR
from taipei_traffic import figures as F

st.set_page_config(page_title="臺北市113年交通事故分析", page_icon="🚦", layout="wide")


# cache_resource：所有 session 共享同一份唯讀 DataFrame，避免免費雲端方案
# 因 cache_data 逐 session 複製資料而耗盡記憶體
@st.cache_resource
def load_data():
    return F.load_web_data()


if not DB_PATH.exists():
    st.error("找不到資料庫，請先執行 `uv run python -m taipei_traffic.pipeline --steps db,models`")
    st.stop()

accidents, parties = load_data()

# ---------------- 側欄篩選器 ----------------
st.sidebar.title("篩選條件")
month_range = st.sidebar.slider("月份範圍", 1, 12, (1, 12))
districts = st.sidebar.multiselect(
    "行政區（不選＝全部）", sorted(accidents["district"].unique())
)
periods = st.sidebar.multiselect("時段（不選＝全部）", TIME_PERIODS)
severities = st.sidebar.multiselect("事故類別（不選＝全部）", ["A1", "A2"])
veh_cats = st.sidebar.multiselect(
    "第一當事人車種大類（不選＝全部）",
    sorted(accidents["vehicle_category"].dropna().unique()),
)

f = F.apply_filters(accidents, month_range, districts, periods, severities, veh_cats)

st.sidebar.caption(f"符合條件：{len(f):,} / {len(accidents):,} 件")

st.title("臺北市 113 年（2024）A1/A2 類交通事故分析")

if f.empty:
    st.warning("目前篩選條件下沒有任何事故，請放寬條件。")
    st.stop()

# ---------------- KPI ----------------
kpi = F.kpi_values(f)
for col, (label, value) in zip(st.columns(4), kpi.items()):
    col.metric(label, f"{value:,}" if isinstance(value, int) else f"{value:.2f}")

tab_map, tab_time, tab_cause, tab_model, tab_data = st.tabs(
    ["🗺️ 事故熱點地圖", "🕒 時間分析", "🚗 肇因與車種", "📈 嚴重度模型", "📋 資料明細"]
)

# ---------------- 地圖（本機 Streamlit 用 pydeck；線上 Gradio 版用 Plotly 地圖）----
with tab_map:
    geo = f.dropna(subset=["lon", "lat"])
    show_points = st.toggle("顯示死亡事故位置（紅點）", value=True)

    ramp_rgb = [
        [205, 226, 251], [134, 182, 239], [85, 152, 231],
        [42, 120, 214], [28, 92, 171], [13, 54, 107],
    ]
    layers = [
        pdk.Layer(
            "HeatmapLayer",
            data=geo[["lon", "lat"]],
            get_position="[lon, lat]",
            radius_pixels=35,
            color_range=ramp_rgb,
        )
    ]
    if show_points:
        fatal = geo[geo["is_fatal"] == 1]
        layers.append(
            pdk.Layer(
                "ScatterplotLayer",
                data=fatal[["lon", "lat", "location", "date"]],
                get_position="[lon, lat]",
                get_radius=60,
                get_fill_color=[208, 59, 59, 220],
                pickable=True,
            )
        )
    st.pydeck_chart(
        pdk.Deck(
            layers=layers,
            initial_view_state=pdk.ViewState(latitude=25.06, longitude=121.55, zoom=11),
            map_style="light",
            tooltip={"text": "{date}\n{location}"},
        ),
        height=560,
    )
    st.caption(
        "藍色深淺代表事故密度（單一色階、由淺至深）；紅點為死亡事故位置，"
        "滑鼠移入可見日期與地點。"
    )

# ---------------- 時間分析 ----------------
with tab_time:
    c1, c2 = st.columns(2)
    c1.plotly_chart(F.monthly_fig(f), width="stretch")
    c2.plotly_chart(F.hourly_fig(f), width="stretch")
    st.plotly_chart(F.weekday_heatmap_fig(f), width="stretch")
    with st.expander("資料表"):
        st.dataframe(F.weekday_heat(f), width="stretch")

# ---------------- 肇因與車種 ----------------
with tab_cause:
    c1, c2 = st.columns(2)
    c1.plotly_chart(F.causes_fig(f), width="stretch")
    c2.plotly_chart(F.vehicles_fig(f, parties), width="stretch")

    cross = F.cross_data(f, parties)
    if not cross.empty:
        st.plotly_chart(F.cross_fig(cross), width="stretch")
        with st.expander("資料表"):
            st.dataframe(cross, width="stretch", hide_index=True)

# ---------------- 嚴重度模型 ----------------
with tab_model:
    st.info("以下為全年度資料的統計檢定與模型結果（不隨側欄篩選變動）。")

    chi_path = MODEL_DIR / "卡方檢定結果.csv"
    or_path = MODEL_DIR / "邏輯迴歸_勝算比.csv"
    if not (chi_path.exists() and or_path.exists()):
        st.warning("尚未產生模型結果，請執行 `uv run python -m taipei_traffic.pipeline --steps models`")
    else:
        st.subheader("卡方獨立性檢定")
        st.dataframe(pd.read_csv(chi_path), width="stretch", hide_index=True)

        st.subheader("死亡事故邏輯迴歸（勝算比與 95% 信賴區間）")
        odds = pd.read_csv(or_path)
        st.plotly_chart(F.or_forest_fig(odds), width="stretch")
        with st.expander("資料表"):
            st.dataframe(odds, width="stretch", hide_index=True)

        st.caption(
            "死亡事故為罕見事件（72／22,368 件），模型用於解讀風險因子方向與"
            "相對強度，非機率預測。"
        )

# ---------------- 資料明細 ----------------
with tab_data:
    show_cols = {
        "date": "日期", "hour": "時", "district": "行政區", "location": "地點",
        "severity": "類別", "deaths_24h": "死亡(24h)", "deaths_2_30d": "死亡(2-30日)",
        "injuries": "受傷", "cause_label": "肇因（第一當事人）",
        "vehicle_label": "車種（第一當事人）", "weather_code": "天候代碼",
    }
    table = f[list(show_cols)].rename(columns=show_cols)
    st.dataframe(table, width="stretch", height=480)
    st.download_button(
        "下載篩選結果 CSV",
        table.to_csv(index=False).encode("utf-8-sig"),
        file_name="taipei_accidents_filtered.csv",
        mime="text/csv",
    )
