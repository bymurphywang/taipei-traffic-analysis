"""臺北市113年（2024）交通事故互動式分析儀表板。

啟動方式：
    uv run streamlit run app/dashboard.py

需先建置資料庫：
    uv run python -m taipei_traffic.pipeline --steps db,models
"""

import sqlite3
import sys
from pathlib import Path

# 部署環境（如 Streamlit Community Cloud）只安裝相依套件、不安裝本專案本身，
# 直接把 src/ 加入匯入路徑，讓本機與雲端行為一致
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pandas as pd
import plotly.graph_objects as go
import pydeck as pdk
import streamlit as st

from taipei_traffic.codes import TIME_PERIODS, WEEKDAY_MAP
from taipei_traffic.config import DB_PATH, MODEL_DIR

# ---- 調色盤（已通過 CVD/對比驗證的固定順序，不足處以直接標籤與資料表補救）----
PAL = ["#2a78d6", "#1baf7a", "#eda100", "#008300", "#4a3aa7", "#e34948", "#e87ba4", "#eb6834"]
BLUE_RAMP = [
    "#cde2fb", "#9ec5f4", "#86b6ef", "#6da7ec", "#5598e7",
    "#3987e5", "#2a78d6", "#256abf", "#1c5cab", "#184f95", "#0d366b",
]
INK = {
    "primary": "#0b0b0b", "secondary": "#52514e", "muted": "#898781",
    "grid": "#e1e0d9", "baseline": "#c3c2b7", "surface": "#fcfcfb",
}
CRITICAL = "#d03b3b"  # 狀態色：死亡事故

WEEKDAY_ORDER = [WEEKDAY_MAP[i] for i in range(7)]

st.set_page_config(page_title="臺北市113年交通事故分析", page_icon="🚦", layout="wide")


# cache_resource：所有 session 共享同一份唯讀 DataFrame，避免免費雲端方案
# 因 cache_data 逐 session 複製資料而耗盡記憶體
@st.cache_resource
def load_data():
    with sqlite3.connect(DB_PATH) as conn:
        accidents = pd.read_sql_query(
            """
            SELECT a.accident_id, a.month, a.hour, a.date, a.weekday_name,
                   a.time_period, a.district, a.location, a.severity,
                   a.deaths_24h, a.deaths_2_30d, a.injuries, a.weather_code,
                   a.is_fatal, a.lon, a.lat, a.cause_code,
                   v.category AS vehicle_category, v.label AS vehicle_label,
                   c.label AS cause_label
            FROM accidents a
            LEFT JOIN vehicle_codes v ON v.code = a.first_vehicle_code
            LEFT JOIN cause_codes c   ON c.code = a.cause_code
            """,
            conn,
        )
        parties = pd.read_sql_query(
            """
            SELECT p.accident_id, p.cause_code_individual,
                   v.label AS vehicle_label
            FROM parties p
            LEFT JOIN vehicle_codes v ON v.code = p.vehicle_code
            """,
            conn,
        )
    # 低基數欄位轉 category dtype 節省記憶體（groupby 會用到的標籤欄維持 object）
    for col in ["district", "time_period", "severity", "weekday_name", "vehicle_category"]:
        accidents[col] = accidents[col].astype("category")
    return accidents, parties


def styled(fig: go.Figure, height: int = 420) -> go.Figure:
    fig.update_layout(
        paper_bgcolor=INK["surface"],
        plot_bgcolor=INK["surface"],
        font=dict(color=INK["secondary"], size=13),
        height=height,
        margin=dict(l=10, r=10, t=30, b=10),
        hoverlabel=dict(bgcolor="white", font_color=INK["primary"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    fig.update_xaxes(gridcolor=INK["grid"], linecolor=INK["baseline"], zerolinecolor=INK["grid"])
    fig.update_yaxes(gridcolor=INK["grid"], linecolor=INK["baseline"], zerolinecolor=INK["grid"])
    return fig


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

f = accidents[accidents["month"].between(*month_range)]
if districts:
    f = f[f["district"].isin(districts)]
if periods:
    f = f[f["time_period"].isin(periods)]
if severities:
    f = f[f["severity"].isin(severities)]
if veh_cats:
    f = f[f["vehicle_category"].isin(veh_cats)]

st.sidebar.caption(f"符合條件：{len(f):,} / {len(accidents):,} 件")

st.title("臺北市 113 年（2024）A1/A2 類交通事故分析")

if f.empty:
    st.warning("目前篩選條件下沒有任何事故，請放寬條件。")
    st.stop()

# ---------------- KPI ----------------
deaths = int(f["deaths_24h"].sum() + f["deaths_2_30d"].sum())
injuries = int(f["injuries"].sum())
k1, k2, k3, k4 = st.columns(4)
k1.metric("事故件數", f"{len(f):,}")
k2.metric("死亡人數（含2-30日）", f"{deaths:,}")
k3.metric("受傷人數", f"{injuries:,}")
k4.metric("平均傷亡／件", f"{(deaths + injuries) / len(f):.2f}")

tab_map, tab_time, tab_cause, tab_model, tab_data = st.tabs(
    ["🗺️ 事故熱點地圖", "🕒 時間分析", "🚗 肇因與車種", "📈 嚴重度模型", "📋 資料明細"]
)

# ---------------- 地圖 ----------------
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

    monthly = f.groupby("month").size().reindex(range(1, 13), fill_value=0)
    fig = go.Figure(
        go.Bar(
            x=[f"{m}月" for m in monthly.index], y=monthly.values,
            marker_color=PAL[0], marker_line_width=0,
            hovertemplate="%{x}：%{y:,} 件<extra></extra>",
        )
    )
    fig.update_layout(title="各月份事故件數", bargap=0.25)
    c1.plotly_chart(styled(fig), width="stretch")

    hourly = f.groupby("hour").size().reindex(range(24), fill_value=0)
    fig = go.Figure(
        go.Scatter(
            x=hourly.index, y=hourly.values, mode="lines+markers",
            line=dict(color=PAL[0], width=2), marker=dict(size=7),
            hovertemplate="%{x} 時：%{y:,} 件<extra></extra>",
        )
    )
    fig.update_layout(title="24 小時事故分布")
    fig.update_xaxes(dtick=2, title="時")
    c2.plotly_chart(styled(fig), width="stretch")

    heat = (
        f.groupby(["hour", "weekday_name"], observed=False).size().unstack(fill_value=0)
        .reindex(index=range(24), columns=WEEKDAY_ORDER, fill_value=0)
    )
    fig = go.Figure(
        go.Heatmap(
            z=heat.values, x=heat.columns, y=heat.index,
            colorscale=[[i / (len(BLUE_RAMP) - 1), c] for i, c in enumerate(BLUE_RAMP)],
            hovertemplate="%{x} %{y} 時：%{z:,} 件<extra></extra>",
            colorbar=dict(title="件數"),
        )
    )
    fig.update_layout(title="小時 × 星期 事故熱力圖")
    fig.update_yaxes(dtick=2, title="時", autorange="reversed")
    st.plotly_chart(styled(fig, height=520), width="stretch")

    with st.expander("資料表"):
        st.dataframe(heat, width="stretch")

# ---------------- 肇因與車種 ----------------
with tab_cause:
    c1, c2 = st.columns(2)

    top_causes = (
        f.dropna(subset=["cause_code"]).groupby(["cause_code", "cause_label"])
        .size().nlargest(10).reset_index(name="count")
    )
    fig = go.Figure(
        go.Bar(
            x=top_causes["count"], y=top_causes["cause_label"], orientation="h",
            marker_color=PAL[0], marker_line_width=0,
            hovertemplate="%{y}：%{x:,} 件<extra></extra>",
        )
    )
    fig.update_layout(title="前 10 大肇因（第一當事人）")
    fig.update_yaxes(autorange="reversed")
    c1.plotly_chart(styled(fig, height=460), width="stretch")

    veh = (
        parties[parties["accident_id"].isin(f["accident_id"])]
        .dropna(subset=["vehicle_label"])
        .groupby("vehicle_label").size().nlargest(10).reset_index(name="count")
    )
    fig = go.Figure(
        go.Bar(
            x=veh["count"], y=veh["vehicle_label"], orientation="h",
            marker_color=PAL[0], marker_line_width=0,
            hovertemplate="%{y}：%{x:,} 人次<extra></extra>",
        )
    )
    fig.update_layout(title="涉入車種前 10 名（全部當事人）")
    fig.update_yaxes(autorange="reversed")
    c2.plotly_chart(styled(fig, height=460), width="stretch")

    # 交叉分析：前5肇因中，個別肇因為該代碼的當事人車種分布（前3車種）
    top5 = (
        f.dropna(subset=["cause_code"]).groupby(["cause_code", "cause_label"])
        .size().nlargest(5).reset_index(name="n")
    )
    fp = parties[parties["accident_id"].isin(f["accident_id"])]
    rows = []
    for _, row in top5.iterrows():
        sub = fp[fp["cause_code_individual"] == row["cause_code"]]
        dist = sub.dropna(subset=["vehicle_label"]).groupby("vehicle_label").size().nlargest(3)
        for veh_label, n in dist.items():
            rows.append(
                {"肇因": row["cause_label"], "車種": veh_label,
                 "涉入人次": n, "佔比": n / len(sub) * 100 if len(sub) else 0}
            )
    cross = pd.DataFrame(rows)
    if not cross.empty:
        vehicles_in_order = list(dict.fromkeys(cross["車種"]))
        fig = go.Figure()
        for i, veh_label in enumerate(vehicles_in_order):
            sub = cross[cross["車種"] == veh_label]
            fig.add_bar(
                x=sub["肇因"], y=sub["涉入人次"], name=veh_label,
                marker_color=PAL[i % len(PAL)], marker_line_width=0,
                customdata=sub["佔比"],
                hovertemplate="%{x}<br>" + veh_label + "：%{y:,} 人次（%{customdata:.1f}%）<extra></extra>",
            )
        fig.update_layout(title="前 5 大肇因 × 涉入車種（各取前 3 名）", barmode="group", bargap=0.25)
        st.plotly_chart(styled(fig, height=460), width="stretch")
        with st.expander("資料表"):
            st.dataframe(
                cross.assign(佔比=cross["佔比"].round(2)),
                width="stretch", hide_index=True,
            )

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
        odds["label"] = odds.apply(
            lambda r: f"{r['變項']} *" if r["p值"] < 0.05 else r["變項"], axis=1
        )
        odds = odds.iloc[::-1]  # 由上而下依原表順序
        fig = go.Figure(
            go.Scatter(
                x=odds["勝算比(OR)"], y=odds["label"], mode="markers",
                marker=dict(color=PAL[0], size=10),
                error_x=dict(
                    type="data", symmetric=False,
                    array=odds["OR 95%CI上界"] - odds["勝算比(OR)"],
                    arrayminus=odds["勝算比(OR)"] - odds["OR 95%CI下界"],
                    color=INK["muted"], thickness=2,
                ),
                customdata=odds["p值"],
                hovertemplate="%{y}<br>OR %{x:.2f}（p=%{customdata:.4f}）<extra></extra>",
            )
        )
        fig.add_vline(x=1, line_dash="dash", line_color=INK["baseline"])
        fig.update_xaxes(type="log", title="勝算比（對數刻度，>1 表死亡風險較高）")
        fig.update_layout(title="風險因子勝算比（* 表 p<0.05；參考組：下午時段、小客車）")
        st.plotly_chart(styled(fig, height=520), width="stretch")
        with st.expander("資料表"):
            st.dataframe(odds.drop(columns="label"), width="stretch", hide_index=True)

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
