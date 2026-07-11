"""共用視覺化模組：Streamlit 與 Gradio 兩個前端使用同一套資料載入、
篩選與 Plotly 圖表邏輯，確保線上 demo 與本機儀表板數字一致。

調色盤為通過 CVD/對比驗證的固定順序；低對比色以直接標籤與資料表補救。
"""

import sqlite3
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go

from .codes import WEEKDAY_MAP
from .config import DB_PATH

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
BLUE_COLORSCALE = [[i / (len(BLUE_RAMP) - 1), c] for i, c in enumerate(BLUE_RAMP)]


def load_web_data(db_path: Path = DB_PATH) -> tuple[pd.DataFrame, pd.DataFrame]:
    """載入儀表板需要的事故與當事人資料（只取會用到的欄位）。"""
    with sqlite3.connect(db_path) as conn:
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
    for col in ["district", "time_period", "severity", "weekday_name", "vehicle_category"]:
        accidents[col] = accidents[col].astype("category")
    return accidents, parties


def apply_filters(
    accidents: pd.DataFrame,
    month_range: tuple[int, int] = (1, 12),
    districts: list[str] | None = None,
    periods: list[str] | None = None,
    severities: list[str] | None = None,
    veh_cats: list[str] | None = None,
) -> pd.DataFrame:
    f = accidents[accidents["month"].between(*month_range)]
    if districts:
        f = f[f["district"].isin(districts)]
    if periods:
        f = f[f["time_period"].isin(periods)]
    if severities:
        f = f[f["severity"].isin(severities)]
    if veh_cats:
        f = f[f["vehicle_category"].isin(veh_cats)]
    return f


def kpi_values(f: pd.DataFrame) -> dict:
    deaths = int(f["deaths_24h"].sum() + f["deaths_2_30d"].sum())
    injuries = int(f["injuries"].sum())
    return {
        "事故件數": len(f),
        "死亡人數（含2-30日）": deaths,
        "受傷人數": injuries,
        "平均傷亡／件": round((deaths + injuries) / len(f), 2) if len(f) else 0,
    }


def style(fig: go.Figure, height: int = 420) -> go.Figure:
    fig.update_layout(
        paper_bgcolor=INK["surface"],
        plot_bgcolor=INK["surface"],
        font=dict(color=INK["secondary"], size=13),
        height=height,
        margin=dict(l=10, r=10, t=40, b=10),
        hoverlabel=dict(bgcolor="white", font_color=INK["primary"]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0),
    )
    fig.update_xaxes(gridcolor=INK["grid"], linecolor=INK["baseline"], zerolinecolor=INK["grid"])
    fig.update_yaxes(gridcolor=INK["grid"], linecolor=INK["baseline"], zerolinecolor=INK["grid"])
    return fig


def monthly_fig(f: pd.DataFrame) -> go.Figure:
    monthly = f.groupby("month").size().reindex(range(1, 13), fill_value=0)
    fig = go.Figure(
        go.Bar(
            x=[f"{m}月" for m in monthly.index], y=monthly.values,
            marker_color=PAL[0], marker_line_width=0,
            hovertemplate="%{x}：%{y:,} 件<extra></extra>",
        )
    )
    fig.update_layout(title="各月份事故件數", bargap=0.25)
    return style(fig)


def hourly_fig(f: pd.DataFrame) -> go.Figure:
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
    return style(fig)


def weekday_heat(f: pd.DataFrame) -> pd.DataFrame:
    return (
        f.groupby(["hour", "weekday_name"], observed=False).size().unstack(fill_value=0)
        .reindex(index=range(24), columns=WEEKDAY_ORDER, fill_value=0)
    )


def weekday_heatmap_fig(f: pd.DataFrame) -> go.Figure:
    heat = weekday_heat(f)
    fig = go.Figure(
        go.Heatmap(
            z=heat.values, x=list(heat.columns), y=list(heat.index),
            colorscale=BLUE_COLORSCALE,
            hovertemplate="%{x} %{y} 時：%{z:,} 件<extra></extra>",
            colorbar=dict(title="件數"),
        )
    )
    fig.update_layout(title="小時 × 星期 事故熱力圖")
    fig.update_yaxes(dtick=2, title="時", autorange="reversed")
    return style(fig, height=520)


def causes_fig(f: pd.DataFrame) -> go.Figure:
    top = (
        f.dropna(subset=["cause_code"]).groupby(["cause_code", "cause_label"])
        .size().nlargest(10).reset_index(name="count")
    )
    fig = go.Figure(
        go.Bar(
            x=top["count"], y=top["cause_label"], orientation="h",
            marker_color=PAL[0], marker_line_width=0,
            hovertemplate="%{y}：%{x:,} 件<extra></extra>",
        )
    )
    fig.update_layout(title="前 10 大肇因（第一當事人）")
    fig.update_yaxes(autorange="reversed")
    return style(fig, height=460)


def vehicles_fig(f: pd.DataFrame, parties: pd.DataFrame) -> go.Figure:
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
    return style(fig, height=460)


def cross_data(f: pd.DataFrame, parties: pd.DataFrame) -> pd.DataFrame:
    """前5肇因中，個別肇因為該代碼的當事人車種分布（各取前3車種）。"""
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
                 "涉入人次": int(n), "佔比": round(n / len(sub) * 100, 2) if len(sub) else 0}
            )
    return pd.DataFrame(rows)


def cross_fig(cross: pd.DataFrame) -> go.Figure:
    fig = go.Figure()
    if not cross.empty:
        vehicles_in_order = list(dict.fromkeys(cross["車種"]))
        for i, veh_label in enumerate(vehicles_in_order):
            sub = cross[cross["車種"] == veh_label]
            fig.add_bar(
                x=sub["肇因"], y=sub["涉入人次"], name=veh_label,
                marker_color=PAL[i % len(PAL)], marker_line_width=0,
                customdata=sub["佔比"],
                hovertemplate="%{x}<br>" + veh_label + "：%{y:,} 人次（%{customdata:.1f}%）<extra></extra>",
            )
    fig.update_layout(title="前 5 大肇因 × 涉入車種（各取前 3 名）", barmode="group", bargap=0.25)
    return style(fig, height=460)


def or_forest_fig(odds: pd.DataFrame) -> go.Figure:
    odds = odds.copy()
    odds["label"] = odds.apply(
        lambda r: f"{r['變項']} *" if r["p值"] < 0.05 else r["變項"], axis=1
    )
    odds = odds.iloc[::-1]
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
    return style(fig, height=520)


def density_map_fig(f: pd.DataFrame, show_fatal: bool = True) -> go.Figure:
    """事故密度地圖（Plotly MapLibre，單一藍色色階）＋死亡事故紅點。"""
    geo = f.dropna(subset=["lon", "lat"])
    fig = go.Figure(
        go.Densitymap(
            lat=geo["lat"], lon=geo["lon"], radius=8,
            colorscale=BLUE_COLORSCALE, showscale=True,
            colorbar=dict(title="密度"),
            hoverinfo="skip", name="事故密度",
        )
    )
    if show_fatal:
        fatal = geo[geo["is_fatal"] == 1]
        fig.add_trace(
            go.Scattermap(
                lat=fatal["lat"], lon=fatal["lon"], mode="markers",
                marker=dict(size=10, color=CRITICAL),
                text=fatal["date"].astype(str) + " " + fatal["location"].astype(str),
                hovertemplate="%{text}<extra>死亡事故</extra>",
                name="死亡事故",
            )
        )
    fig.update_layout(
        map=dict(style="carto-positron", center=dict(lat=25.06, lon=121.55), zoom=10.5),
        height=560, margin=dict(l=0, r=0, t=10, b=0),
        legend=dict(orientation="h", yanchor="bottom", y=1.01, x=0),
        paper_bgcolor=INK["surface"],
    )
    return fig
