"""臺北市113年（2024）交通事故互動式分析儀表板（Gradio 版，線上 demo 用）。

Hugging Face Spaces 免費方案（2026 起）僅支援 Gradio SDK，本檔為線上入口；
圖表與篩選邏輯與 Streamlit 版共用 taipei_traffic.figures，數字完全一致。

本機啟動：
    uv run python app/gradio_app.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import gradio as gr
import pandas as pd
import plotly.graph_objects as go

from taipei_traffic.codes import TIME_PERIODS
from taipei_traffic.config import MODEL_DIR
from taipei_traffic import figures as F

ACCIDENTS, PARTIES = F.load_web_data()
DISTRICTS = sorted(ACCIDENTS["district"].unique())
VEH_CATS = sorted(ACCIDENTS["vehicle_category"].dropna().unique())

_CHI_PATH = MODEL_DIR / "卡方檢定結果.csv"
_OR_PATH = MODEL_DIR / "邏輯迴歸_勝算比.csv"
CHI_DF = pd.read_csv(_CHI_PATH) if _CHI_PATH.exists() else None
ODDS_DF = pd.read_csv(_OR_PATH) if _OR_PATH.exists() else None

_DETAIL_COLS = {
    "date": "日期", "hour": "時", "district": "行政區", "location": "地點",
    "severity": "類別", "deaths_24h": "死亡(24h)", "deaths_2_30d": "死亡(2-30日)",
    "injuries": "受傷", "cause_label": "肇因（第一當事人）",
    "vehicle_label": "車種（第一當事人）",
}


def _kpi_html(kpi: dict) -> str:
    cells = "".join(
        f"""<div style="flex:1;min-width:150px;background:#f9f9f7;border:1px solid #e1e0d9;
                    border-radius:8px;padding:12px 16px;">
              <div style="color:#52514e;font-size:13px;">{label}</div>
              <div style="color:#0b0b0b;font-size:26px;font-weight:700;">
                {f'{value:,}' if isinstance(value, int) else f'{value:.2f}'}
              </div>
            </div>"""
        for label, value in kpi.items()
    )
    return f'<div style="display:flex;gap:12px;flex-wrap:wrap;">{cells}</div>'


def _empty_fig(msg: str) -> go.Figure:
    fig = go.Figure()
    fig.add_annotation(text=msg, showarrow=False, font=dict(size=16, color="#52514e"))
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(paper_bgcolor="#fcfcfb", plot_bgcolor="#fcfcfb", height=300)
    return fig


def refresh(m_lo, m_hi, districts, periods, severities, veh_cats, show_fatal):
    lo, hi = int(min(m_lo, m_hi)), int(max(m_lo, m_hi))
    f = F.apply_filters(ACCIDENTS, (lo, hi), districts, periods, severities, veh_cats)

    if f.empty:
        empty = _empty_fig("目前篩選條件下沒有任何事故，請放寬條件")
        return (
            '<div style="color:#d03b3b;">目前篩選條件下沒有任何事故，請放寬條件。</div>',
            empty, empty, empty, empty, empty, empty, empty,
            pd.DataFrame(), pd.DataFrame(),
        )

    cross = F.cross_data(f, PARTIES)

    detail = f[list(_DETAIL_COLS)].rename(columns=_DETAIL_COLS).head(1000)
    for col in ["行政區", "類別"]:
        detail[col] = detail[col].astype(str)

    return (
        _kpi_html(F.kpi_values(f)),
        F.density_map_fig(f, show_fatal=bool(show_fatal)),
        F.monthly_fig(f),
        F.hourly_fig(f),
        F.weekday_heatmap_fig(f),
        F.causes_fig(f),
        F.vehicles_fig(f, PARTIES),
        F.cross_fig(cross),
        cross,
        detail,
    )


with gr.Blocks(title="臺北市113年交通事故分析") as demo:
    gr.Markdown(
        "# 🚦 臺北市 113 年（2024）A1/A2 類交通事故分析\n"
        "22,368 件事故／51,810 筆當事人紀錄 · 資料來源：政府資料開放平台 · "
        "[原始碼與研究報告](https://github.com/bymurphywang/taipei-traffic-analysis)"
    )

    with gr.Row():
        m_lo = gr.Slider(1, 12, value=1, step=1, label="起始月")
        m_hi = gr.Slider(1, 12, value=12, step=1, label="結束月")
        d_sel = gr.Dropdown(DISTRICTS, multiselect=True, label="行政區（空＝全部）")
        p_sel = gr.Dropdown(TIME_PERIODS, multiselect=True, label="時段（空＝全部）")
        s_sel = gr.Dropdown(["A1", "A2"], multiselect=True, label="事故類別（空＝全部）")
        v_sel = gr.Dropdown(VEH_CATS, multiselect=True, label="第一當事人車種大類（空＝全部）")

    kpi_html = gr.HTML()

    with gr.Tabs():
        with gr.Tab("🗺️ 事故熱點地圖"):
            show_fatal = gr.Checkbox(value=True, label="顯示死亡事故位置（紅點）")
            map_plot = gr.Plot(show_label=False)
            gr.Markdown("藍色深淺代表事故密度（單一色階、由淺至深）；紅點滑入可見日期與地點。")
        with gr.Tab("🕒 時間分析"):
            with gr.Row():
                monthly_plot = gr.Plot(show_label=False)
                hourly_plot = gr.Plot(show_label=False)
            heat_plot = gr.Plot(show_label=False)
        with gr.Tab("🚗 肇因與車種"):
            with gr.Row():
                causes_plot = gr.Plot(show_label=False)
                vehicles_plot = gr.Plot(show_label=False)
            cross_plot = gr.Plot(show_label=False)
            cross_table = gr.Dataframe(label="交叉統計資料表", interactive=False)
        with gr.Tab("📈 嚴重度模型"):
            gr.Markdown(
                "以下為**全年度**資料的統計檢定與模型結果（不隨篩選變動）。"
                "死亡事故為罕見事件（72／22,368 件），模型用於解讀風險因子方向與"
                "相對強度，非機率預測。"
            )
            if CHI_DF is not None:
                gr.Dataframe(value=CHI_DF, label="卡方獨立性檢定", interactive=False)
            if ODDS_DF is not None:
                gr.Plot(value=F.or_forest_fig(ODDS_DF), show_label=False)
                gr.Dataframe(value=ODDS_DF, label="勝算比與 95% 信賴區間", interactive=False)
        with gr.Tab("📋 資料明細"):
            detail_table = gr.Dataframe(label="篩選結果（最多顯示 1,000 筆）", interactive=False)

    inputs = [m_lo, m_hi, d_sel, p_sel, s_sel, v_sel, show_fatal]
    outputs = [
        kpi_html, map_plot, monthly_plot, hourly_plot, heat_plot,
        causes_plot, vehicles_plot, cross_plot, cross_table, detail_table,
    ]
    for comp in inputs:
        comp.change(refresh, inputs, outputs)
    demo.load(refresh, inputs, outputs)


if __name__ == "__main__":
    demo.launch()
