"""統計檢定與事故嚴重度模型。

1. 卡方獨立性檢定：雨天／時段／第一當事人車種大類 × 是否為死亡事故
2. 邏輯迴歸：以事故層級預測「是否為死亡事故」（24小時內或2-30日內有人死亡）

死亡事故僅 72 件（佔 0.32%），屬罕見事件：迴歸結果著重方向與相對風險
（勝算比），不宜直接作為機率預測器使用。
"""

from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats as scipy_stats

from .config import DB_PATH, MODEL_DIR
from .db import connect

_MODEL_QUERY = """
SELECT a.is_fatal, a.is_rain, a.time_period, a.weekday, a.speed_limit,
       p.age, p.gender_code, p.vehicle_category
FROM accidents a
JOIN parties p ON p.accident_id = a.accident_id AND p.party_seq = 1
"""

# 死亡事故稀少，車種合併為大類以避免完全分離
_VEHICLE_GROUPS = {
    "機車": "機車",
    "小客車": "小客車",
    "小貨車": "小貨車",
    "大客車": "大型車",
    "大貨車": "大型車",
    "聯結車": "大型車",
    "曳引車": "大型車",
    "慢車": "慢車",
    "人（行人/乘客）": "其他",
    "其他車": "其他",
    "特種車": "其他",
    "軍車": "其他",
}

_VEHICLE_REF = "小客車"
_PERIOD_REF = "下午 (12:00-17:59)"


def load_model_data(db_path: Path = DB_PATH) -> pd.DataFrame:
    with connect(db_path) as conn:
        df = pd.read_sql_query(_MODEL_QUERY, conn)
    df["vehicle_group"] = df["vehicle_category"].map(_VEHICLE_GROUPS)
    df["is_weekend"] = (df["weekday"] >= 5).astype(int)
    return df


def _cramers_v(table: np.ndarray, chi2: float) -> float:
    n = table.sum()
    k = min(table.shape) - 1
    return float(np.sqrt(chi2 / (n * k))) if k > 0 else float("nan")


def chi_square_tests(df: pd.DataFrame) -> pd.DataFrame:
    """對是否死亡事故做三組卡方獨立性檢定。"""
    tests = {
        "雨天 × 是否死亡事故": df["is_rain"],
        "時段 × 是否死亡事故": df["time_period"],
        "第一當事人車種大類 × 是否死亡事故": df["vehicle_group"],
    }
    rows = []
    for name, factor in tests.items():
        table = pd.crosstab(factor, df["is_fatal"]).to_numpy()
        chi2, p, dof, _ = scipy_stats.chi2_contingency(table)
        rows.append(
            {
                "檢定": name,
                "卡方值": round(chi2, 3),
                "自由度": dof,
                "p值": round(p, 5),
                "Cramér's V": round(_cramers_v(table, chi2), 4),
                "顯著(α=0.05)": "是" if p < 0.05 else "否",
            }
        )
    return pd.DataFrame(rows)


def _design_matrix(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    d = df[
        df["gender_code"].isin([1, 2])
        & df["age"].notna()
        & df["speed_limit"].notna()
        & df["vehicle_group"].notna()
    ].copy()

    X = pd.DataFrame(index=d.index)
    X["雨天"] = d["is_rain"]
    X["週末"] = d["is_weekend"]
    X["年齡(每+10歲)"] = d["age"] / 10
    X["男性"] = (d["gender_code"] == 1).astype(int)
    X["速限(每+10km/h)"] = d["speed_limit"] / 10

    period_dummies = pd.get_dummies(d["time_period"], prefix="時段").astype(int)
    period_dummies = period_dummies.drop(columns=f"時段_{_PERIOD_REF}")
    X = pd.concat([X, period_dummies], axis=1)

    vehicle_dummies = pd.get_dummies(d["vehicle_group"], prefix="車種").astype(int)
    vehicle_dummies = vehicle_dummies.drop(columns=f"車種_{_VEHICLE_REF}")
    X = pd.concat([X, vehicle_dummies], axis=1)

    X = sm.add_constant(X)
    return X, d["is_fatal"]


def severity_logit(df: pd.DataFrame):
    """配適死亡事故邏輯迴歸，回傳 (fit結果, 勝算比表)。"""
    X, y = _design_matrix(df)
    fit = sm.Logit(y, X.astype(float)).fit(disp=False)

    conf = fit.conf_int()
    odds = pd.DataFrame(
        {
            "變項": fit.params.index,
            "係數": fit.params.round(4).values,
            "勝算比(OR)": np.exp(fit.params).round(3).values,
            "OR 95%CI下界": np.exp(conf[0]).round(3).values,
            "OR 95%CI上界": np.exp(conf[1]).round(3).values,
            "p值": fit.pvalues.round(5).values,
        }
    )
    odds = odds[odds["變項"] != "const"].reset_index(drop=True)
    return fit, odds


def run_all(db_path: Path = DB_PATH, out_dir: Path = MODEL_DIR) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    df = load_model_data(db_path)

    chi = chi_square_tests(df)
    chi.to_csv(out_dir / "卡方檢定結果.csv", index=False, encoding="utf-8-sig")
    print("✓ 卡方檢定結果.csv")
    print(chi.to_string(index=False))

    fit, odds = severity_logit(df)
    odds.to_csv(out_dir / "邏輯迴歸_勝算比.csv", index=False, encoding="utf-8-sig")
    print("\n✓ 邏輯迴歸_勝算比.csv")
    print(odds.to_string(index=False))

    summary_path = out_dir / "邏輯迴歸_模型摘要.txt"
    n_events = int(df["is_fatal"].sum())
    caveat = (
        "註：死亡事故為罕見事件（{} 件 / {} 件，約 {:.2%}），本模型用於解讀風險\n"
        "因子方向與相對強度（勝算比），非機率預測器。參考組別：時段=下午、\n"
        "車種=小客車。\n\n"
    ).format(n_events, len(df), n_events / len(df))
    summary_path.write_text(caveat + str(fit.summary()), encoding="utf-8")
    print(f"✓ {summary_path.name}（McFadden pseudo R² = {fit.prsquared:.3f}）")
