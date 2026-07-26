# -*- coding: utf-8 -*-
"""
bonus.py — 加分项（方案 §7 待办 + §8 方法储备）

1. 逐时段购电计划表/储能调度表导出（Q1(2)、Q2(2)、Q3(2) 附录，CSV 存 results/）
2. 灵敏度实验4：负荷增长 50%±10% 扰动对 Q3(1) 配置的稳健性
3. 模型讨论：A 园区自由配置（可建风电）vs 纯光伏对比
4. 差分进化（DE）交叉验证 Q3(1)：智能算法外层寻优 vs 单 LP 全局最优

运行：python src/bonus.py
"""

import os

import numpy as np
import pandas as pd
from scipy.optimize import differential_evolution

import model
from model import TOU_PRICE, solve_operation, solve_sizing
from utils import FIG_DIR, load_monthly, load_typical_day, typical_day_power

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
os.makedirs(RESULTS_DIR, exist_ok=True)
HOURS = np.arange(24)


def export_schedule_tables(parks):
    """附录表：逐时段购电计划 + 储能调度（方案 §7 待办）。"""
    print("【导出附录调度表】")

    # Q1(2)：各园区 50kW/100kWh
    for p, d in parks.items():
        r = solve_operation(d["L"], d["W"], d["S"], 50.0, 100.0)
        df = pd.DataFrame({
            "时段(h)": HOURS,
            "负荷(kW)": d["L"],
            "风电消纳(kW)": np.round(r["Wu"], 2),
            "光伏消纳(kW)": np.round(r["Su"], 2),
            "网购电(kW)": np.round(r["buy_t"], 2),
            "充电(kW)": np.round(r["ch"], 2),
            "放电(kW)": np.round(r["dis"], 2),
            "时段末SOC(kWh)": np.round(r["E"][1:], 2),
        })
        path = os.path.join(RESULTS_DIR, f"附录_Q12_调度表_{p}.csv")
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print("  saved:", os.path.basename(path))

    # Q2(2)：联合园区（最优储能为 0，购电计划即净负荷正值部分）
    L = sum(d["L"] for d in parks.values())
    W = sum(d["W"] for d in parks.values())
    S = sum(d["S"] for d in parks.values())
    r = solve_operation(L, W, S, 0.0, 0.0)
    df = pd.DataFrame({
        "时段(h)": HOURS,
        "联合负荷(kW)": L,
        "风电消纳(kW)": np.round(r["Wu"], 2),
        "光伏消纳(kW)": np.round(r["Su"], 2),
        "网购电(kW)": np.round(r["buy_t"], 2),
        "弃电(kW)": np.round(W + S - r["Wu"] - r["Su"], 2),
    })
    path = os.path.join(RESULTS_DIR, "附录_Q22_联合园区购电计划.csv")
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print("  saved:", os.path.basename(path))

    # Q3(2)：园区C 2 月/8 月典型日（Q3(2) 最优配置下）
    monthly = load_monthly()
    mk_w = {m: monthly[m]["C_w"] for m in range(12)}
    mk_s = {m: monthly[m]["C_pv"] for m in range(12)}
    rr = model.solve_sizing_annual(parks["C"]["L"] * 1.5, mk_w, mk_s)
    for m in (1, 7):
        W = monthly[m]["C_w"] * rr["P_w"]
        S = monthly[m]["C_pv"] * rr["P_pv"]
        r = solve_operation(parks["C"]["L"] * 1.5, W, S,
                            rr["P_ess"], rr["E_ess"],
                            price_buy=TOU_PRICE, c_w=0.0, c_s=0.0)
        df = pd.DataFrame({
            "时段(h)": HOURS,
            "负荷(kW)": parks["C"]["L"] * 1.5,
            "风电消纳(kW)": np.round(r["Wu"], 2),
            "光伏消纳(kW)": np.round(r["Su"], 2),
            "网购电(kW)": np.round(r["buy_t"], 2),
            "充电(kW)": np.round(r["ch"], 2),
            "放电(kW)": np.round(r["dis"], 2),
            "时段末SOC(kWh)": np.round(r["E"][1:], 2),
            "分时电价(元/kWh)": TOU_PRICE,
        })
        path = os.path.join(RESULTS_DIR, f"附录_Q32_园区C_{m + 1}月调度表.csv")
        df.to_csv(path, index=False, encoding="utf-8-sig")
        print("  saved:", os.path.basename(path))


def sensitivity_load_robustness(parks):
    """灵敏度实验4：负荷增长 50%±10% 扰动对 Q3(1) 配置的影响（方案 §8.5.2）。"""
    print("\n【灵敏度实验4：负荷增长率 40%/45%/50%/55%/60% 对 Q3(1) 的影响】")
    pu = load_typical_day()
    pu_map = {
        "A": (None, pu["A_pv"]),
        "B": (pu["B_w"], None),
        "C": (pu["C_w"], pu["C_pv"]),
    }
    rows = []
    for growth in (0.40, 0.45, 0.50, 0.55, 0.60):
        for p, d in parks.items():
            r = solve_sizing(d["L"] * (1 + growth), *pu_map[p], price_buy=1.0)
            rows.append({
                "负荷增长率": f"+{growth:.0%}",
                "园区": p,
                "风电(kW)": round(r["P_w"], 1),
                "光伏(kW)": round(r["P_pv"], 1),
                "储能功率(kW)": round(r["P_ess"], 1),
                "储能容量(kWh)": round(r["E_ess"], 1),
                "日总成本(元)": round(r["cost"], 1),
            })
            print(f"  +{growth:.0%} {p}: 风{r['P_w']:.0f} 光{r['P_pv']:.0f} "
                  f"储{r['P_ess']:.0f}/{r['E_ess']:.0f} 成本{r['cost']:.1f}")
    path = os.path.join(RESULTS_DIR, "灵敏度4_负荷扰动_Q31.csv")
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
    print("  saved:", os.path.basename(path))


def free_config_discussion(parks):
    """模型讨论素材：A 园区解除"保持原电源类型"约束、允许自建风电。

    A 无测风数据，借用 B 园区风电 pu 曲线作代表（同区域风资源近似）。
    结论：风电 1584 kW 为主、日总成本 3945 元，显著低于纯光伏方案，
    用于论文"模型讨论"论证风电经济性碾压光伏（方案 §5 约定 2）。
    """
    print("\n【模型讨论：A 园区自由配置（可建风电）vs 纯光伏】")
    pu = load_typical_day()
    L = parks["A"]["L"] * 1.5
    base = solve_sizing(L, None, pu["A_pv"], price_buy=1.0)
    free = solve_sizing(L, pu["B_w"], pu["A_pv"], price_buy=1.0)
    rows = []
    for name, r in [("纯光伏（原口径）", base), ("自由配置（借用B风pu）", free)]:
        print(f"  {name}: 风电 {r['P_w']:.0f} kW, 光伏 {r['P_pv']:.0f} kW, "
              f"储能 {r['P_ess']:.0f}/{r['E_ess']:.0f}, 日总成本 {r['cost']:.1f} 元")
        rows.append({
            "方案": name,
            "风电(kW)": round(r["P_w"], 1), "光伏(kW)": round(r["P_pv"], 1),
            "储能(kW/kWh)": f"{r['P_ess']:.0f}/{r['E_ess']:.0f}",
            "日总成本(元)": round(r["cost"], 1),
        })
    print(f"  自由配置日省 {base['cost'] - free['cost']:.1f} 元"
          f"（{(base['cost'] - free['cost']) / base['cost']:.1%}）")
    path = os.path.join(RESULTS_DIR, "模型讨论_A自由配置对比.csv")
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
    print("  saved:", os.path.basename(path))


def de_cross_validation(parks):
    """差分进化交叉验证 Q3(1)：外层 DE 搜容量、内层 LP 算运行成本。

    LP 单步即得全局最优；DE 作为智能算法代表独立复搜，两套结果一致
    可增强论文说服力（方案 §8.2.4 可选加分项）。
    """
    print("\n【Q3(1) 差分进化交叉验证（外层容量 + 内层运行 LP）】")
    pu = load_typical_day()
    cases = {
        "A": (None, pu["A_pv"], [(0, 0), (0, 4000), (0, 2000), (0, 12000)]),
        "B": (pu["B_w"], None, [(0, 3000), (0, 0), (0, 2000), (0, 12000)]),
        "C": (pu["C_w"], pu["C_pv"], [(0, 3000), (0, 2000), (0, 2000), (0, 12000)]),
    }
    rows = []
    for p, d in parks.items():
        pu_w, pu_s, bounds = cases[p]
        L = d["L"] * 1.5

        def daily_cost(x):
            P_w, P_pv, P_ess, E_ess = x
            if (P_ess == 0) != (E_ess == 0):
                return 1e9  # 功率/容量须同零同非零
            W = pu_w * P_w if pu_w is not None else np.zeros(24)
            S = pu_s * P_pv if pu_s is not None else np.zeros(24)
            r = solve_operation(L, W, S, P_ess, E_ess,
                                price_buy=1.0, c_w=0.0, c_s=0.0)
            return (r["cost"]
                    + (model.ESS_P_COST * P_ess + model.ESS_E_COST * E_ess)
                    / (model.ESS_LIFE * 365)
                    + (model.WIND_COST * P_w + model.PV_COST * P_pv)
                    / (model.INV_PAYBACK * 365))

        de = differential_evolution(daily_cost, bounds, seed=42, tol=1e-8,
                                    popsize=20, maxiter=200, polish=True)
        lp = solve_sizing(L, pu_w, pu_s, price_buy=1.0)
        print(f"  {p}: DE 风{de.x[0]:.0f}/光{de.x[1]:.0f}/储{de.x[2]:.0f}-{de.x[3]:.0f}"
              f" 成本{de.fun:.1f} | LP {lp['P_w']:.0f}/{lp['P_pv']:.0f}/"
              f"{lp['P_ess']:.0f}-{lp['E_ess']:.0f} 成本{lp['cost']:.1f}"
              f" | 偏差 {abs(de.fun - lp['cost']) / lp['cost']:.2%}")
        rows.append({
            "园区": p,
            "DE风电(kW)": round(de.x[0], 1), "DE光伏(kW)": round(de.x[1], 1),
            "DE储能(kW/kWh)": f"{de.x[2]:.0f}/{de.x[3]:.0f}",
            "DE日总成本(元)": round(de.fun, 1),
            "LP风电(kW)": round(lp["P_w"], 1), "LP光伏(kW)": round(lp["P_pv"], 1),
            "LP储能(kW/kWh)": f"{lp['P_ess']:.0f}/{lp['E_ess']:.0f}",
            "LP日总成本(元)": round(lp["cost"], 1),
            "成本偏差": f"{abs(de.fun - lp['cost']) / lp['cost']:.2%}",
        })
    path = os.path.join(RESULTS_DIR, "交叉验证_Q31_DE_vs_LP.csv")
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
    print("  saved:", os.path.basename(path))


if __name__ == "__main__":
    parks = typical_day_power()
    export_schedule_tables(parks)
    sensitivity_load_robustness(parks)
    free_config_discussion(parks)
    de_cross_validation(parks)
    print("\n加分项全部完成，结果见 results/")
