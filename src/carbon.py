# -*- coding: utf-8 -*-
"""
carbon.py — 碳排放分析（加分项）

在所有方案的经济性分析基础上，增加碳排放维度：
  - 电网购电碳排放（中国电网平均排放因子 0.581 kg CO₂/kWh）
  - 储能设备隐含碳（制造环节，按寿命 10 年日分摊）
  - 风光发电运行碳排放视为 0

运行：python src/carbon.py
"""

import os
import numpy as np
import pandas as pd

import model
from model import solve_operation, solve_sizing, solve_sizing_annual
from solve import (
    ESS_DAILY, analytic_baseline, sweep_storage, q1, q2, q3,
)
from utils import check_power_balance, load_monthly, load_typical_day, typical_day_power
from utils import FIG_DIR as _UNUSED

# ---- 碳排放因子 ----
GRID_EMISSION = 0.581      # 中国电网平均 CO₂ 排放因子 (kg/kWh)，2023 年
ESS_EMBODIED_E = 120.0     # 储能隐含碳 能量部分 (kg CO₂/kWh)
ESS_EMBODIED_P = 50.0      # 储能隐含碳 功率部分 (kg CO₂/kW)
ESS_LIFE_DAYS = 10 * 365   # 储能寿命（天）

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
os.makedirs(RESULTS_DIR, exist_ok=True)


def storage_carbon_daily(P_ess, E_ess):
    """储能隐含碳日分摊 (kg CO₂/日)。"""
    return (ESS_EMBODIED_P * P_ess + ESS_EMBODIED_E * E_ess) / ESS_LIFE_DAYS


def emission_report(parks):
    """主报告：各方案碳排放对比。"""
    print("=" * 65)
    print("碳排放分析")
    print("=" * 65)
    print(f"电网排放因子: {GRID_EMISSION} kg CO2/kWh")
    print(f"储能隐含碳: {ESS_EMBODIED_P} kg/kW + {ESS_EMBODIED_E} kg/kWh (寿命10年日分摊)")
    print()

    rows = []

    # ---- Q1(1) 无储能基线 ----
    print("【Q1(1) 无储能基线碳排放】")
    print(f"{'园区':<4}{'网购电kWh':>10}{'电网排放kg':>12}{'单位排放g/kWh':>14}")
    for p, d in parks.items():
        b = analytic_baseline(d["L"], d["W"], d["S"])
        grid_emis = b["buy"] * GRID_EMISSION
        unit_emis = grid_emis / d["L"].sum() * 1000  # g/kWh
        print(f"{p:<4}{b['buy']:>10.0f}{grid_emis:>12.1f}{unit_emis:>14.1f}")
        rows.append({"场景": f"Q1(1) 基线", "园区": p,
                     "网购电(kWh)": round(b["buy"], 1),
                     "电网排放(kgCO2)": round(grid_emis, 1),
                     "储能隐含碳(kgCO2)": 0.0,
                     "总排放(kgCO2)": round(grid_emis, 1),
                     "单位排放(g/kWh)": round(unit_emis, 1)})

    # ---- Q1(2) 50kW/100kWh ----
    print("\n【Q1(2) 配 50kW/100kWh 碳排放】")
    print(f"{'园区':<4}{'网购电kWh':>10}{'电网排放kg':>12}{'储能隐含碳':>12}{'总排放kg':>12}{'减排量':>10}")
    for p, d in parks.items():
        r = solve_operation(d["L"], d["W"], d["S"], 50.0, 100.0)
        b = analytic_baseline(d["L"], d["W"], d["S"])
        grid_emis = r["buy"] * GRID_EMISSION
        ess_carbon = storage_carbon_daily(50, 100)
        total = grid_emis + ess_carbon
        reduction = b["buy"] * GRID_EMISSION - total
        print(f"{p:<4}{r['buy']:>10.0f}{grid_emis:>12.1f}{ess_carbon:>12.2f}"
              f"{total:>12.1f}{reduction:>+10.1f}")
        rows.append({"场景": "Q1(2) 50kW/100kWh", "园区": p,
                     "网购电(kWh)": round(float(r["buy"]), 1),
                     "电网排放(kgCO2)": round(grid_emis, 1),
                     "储能隐含碳(kgCO2)": round(ess_carbon, 2),
                     "总排放(kgCO2)": round(total, 1),
                     "单位排放(g/kWh)": round(total / d["L"].sum() * 1000, 1)})
        check_power_balance(r, d["L"], 50.0, 100.0)

    # ---- Q1(3) 最优储能 ----
    print("\n【Q1(3) 最优储能配置碳排放】")
    print(f"{'园区':<4}{'配置kW/kWh':>14}{'网购电kWh':>10}{'电网排放kg':>12}{'储能隐含碳':>12}{'总排放kg':>12}{'较基线减排':>12}")
    for p, d in parks.items():
        s = sweep_storage(d["L"], d["W"], d["S"], (0, 200, 10), (0, 400, 20))
        b = analytic_baseline(d["L"], d["W"], d["S"])
        r = solve_operation(d["L"], d["W"], d["S"], s["P_opt"], s["E_opt"])
        grid_emis = r["buy"] * GRID_EMISSION
        ess_carbon = storage_carbon_daily(s["P_opt"], s["E_opt"])
        total = grid_emis + ess_carbon
        base_emis = b["buy"] * GRID_EMISSION
        reduction = base_emis - total
        cfg = f"{s['P_opt']:.0f}/{s['E_opt']:.0f}"
        print(f"{p:<4}{cfg:>14}{r['buy']:>10.0f}{grid_emis:>12.1f}{ess_carbon:>12.2f}"
              f"{total:>12.1f}{reduction:>+12.1f}")
        rows.append({"场景": "Q1(3) 最优储能", "园区": p,
                     "网购电(kWh)": round(float(r["buy"]), 1),
                     "电网排放(kgCO2)": round(grid_emis, 1),
                     "储能隐含碳(kgCO2)": round(ess_carbon, 2),
                     "总排放(kgCO2)": round(total, 1),
                     "单位排放(g/kWh)": round(total / d["L"].sum() * 1000, 1)})

    # ---- Q2 联合运营 ----
    print("\n【Q2 联合运营碳排放】")
    L = sum(d["L"] for d in parks.values())
    W = sum(d["W"] for d in parks.values())
    S = sum(d["S"] for d in parks.values())

    bi = [analytic_baseline(d["L"], d["W"], d["S"]) for d in parks.values()]
    bj = analytic_baseline(L, W, S)
    indep_grid = sum(b["buy"] for b in bi) * GRID_EMISSION
    joint_grid = bj["buy"] * GRID_EMISSION
    print(f"  独立合计: 网购电 {sum(b['buy'] for b in bi):.0f} kWh, "
          f"电网排放 {indep_grid:.1f} kgCO2")
    print(f"  联合运营: 网购电 {bj['buy']:.0f} kWh, "
          f"电网排放 {joint_grid:.1f} kgCO2, "
          f"减排 {indep_grid - joint_grid:.1f} kgCO2 ({(indep_grid - joint_grid) / indep_grid * 100:.1f}%)")

    rows.append({"场景": "Q2 独立合计", "园区": "合计",
                 "网购电(kWh)": round(sum(b["buy"] for b in bi), 1),
                 "电网排放(kgCO2)": round(indep_grid, 1),
                 "储能隐含碳(kgCO2)": 0.0,
                 "总排放(kgCO2)": round(indep_grid, 1),
                 "单位排放(g/kWh)": round(indep_grid / L.sum() * 1000, 1)})
    rows.append({"场景": "Q2 联合运营", "园区": "合计",
                 "网购电(kWh)": round(float(bj["buy"]), 1),
                 "电网排放(kgCO2)": round(joint_grid, 1),
                 "储能隐含碳(kgCO2)": 0.0,
                 "总排放(kgCO2)": round(joint_grid, 1),
                 "单位排放(g/kWh)": round(joint_grid / L.sum() * 1000, 1)})

    # ---- Q3(1) 风光储配置 ----
    print("\n【Q3(1) 风光储配置碳排放（负荷×1.5，固定电价）】")
    pu = load_typical_day()
    pu_map = {"A": (None, pu["A_pv"]), "B": (pu["B_w"], None), "C": (pu["C_w"], pu["C_pv"])}

    print(f"{'园区':<6}{'网购电kWh':>10}{'电网排放kg':>12}{'储能隐含碳':>12}{'总排放kg':>12}{'单位排放g/kWh':>14}")
    for p, d in parks.items():
        r = solve_sizing(d["L"] * 1.5, *pu_map[p], price_buy=1.0)
        W_arr = pu_map[p][0] * r["P_w"] if pu_map[p][0] is not None else np.zeros(24)
        S_arr = pu_map[p][1] * r["P_pv"] if pu_map[p][1] is not None else np.zeros(24)
        op = solve_operation(d["L"] * 1.5, W_arr, S_arr, r["P_ess"], r["E_ess"],
                             price_buy=1.0, c_w=0.0, c_s=0.0)
        grid_emis = op["buy"] * GRID_EMISSION
        ess_carbon = storage_carbon_daily(r["P_ess"], r["E_ess"])
        total = grid_emis + ess_carbon
        unit = total / (d["L"].sum() * 1.5) * 1000
        print(f"{p:<6}{op['buy']:>10.0f}{grid_emis:>12.1f}{ess_carbon:>12.2f}"
              f"{total:>12.1f}{unit:>14.1f}")
        rows.append({"场景": "Q3(1) 风光储", "园区": p,
                     "网购电(kWh)": round(float(op["buy"]), 1),
                     "电网排放(kgCO2)": round(grid_emis, 1),
                     "储能隐含碳(kgCO2)": round(ess_carbon, 2),
                     "总排放(kgCO2)": round(total, 1),
                     "单位排放(g/kWh)": round(unit, 1)})

    # ---- 联合 Q3(1) ----
    L_j = sum(d["L"] for d in parks.values()) * 1.5
    pu_w_j = (1000 * pu["B_w"] + 500 * pu["C_w"]) / 1500
    pu_s_j = (750 * pu["A_pv"] + 600 * pu["C_pv"]) / 1350
    rj = solve_sizing(L_j, pu_w_j, pu_s_j, price_buy=1.0)
    Wj = pu_w_j * rj["P_w"]
    Sj = pu_s_j * rj["P_pv"]
    opj = solve_operation(L_j, Wj, Sj, rj["P_ess"], rj["E_ess"],
                          price_buy=1.0, c_w=0.0, c_s=0.0)
    grid_emis_j = opj["buy"] * GRID_EMISSION
    ess_carbon_j = storage_carbon_daily(rj["P_ess"], rj["E_ess"])
    total_j = grid_emis_j + ess_carbon_j
    unit_j = total_j / L_j.sum() * 1000
    print(f"{'联合':<6}{opj['buy']:>10.0f}{grid_emis_j:>12.1f}{ess_carbon_j:>12.2f}"
          f"{total_j:>12.1f}{unit_j:>14.1f}")
    rows.append({"场景": "Q3(1) 联合", "园区": "联合",
                 "网购电(kWh)": round(float(opj["buy"]), 1),
                 "电网排放(kgCO2)": round(grid_emis_j, 1),
                 "储能隐含碳(kgCO2)": round(ess_carbon_j, 2),
                 "总排放(kgCO2)": round(total_j, 1),
                 "单位排放(g/kWh)": round(unit_j, 1)})

    # ---- Q3(2) 12月分时电价 ----
    print("\n【Q3(2) 12月+分时电价碳排放】")
    monthly = load_monthly()
    print(f"{'园区':<6}{'网购电kWh/年':>14}{'电网排放kg/年':>16}{'储能隐含碳':>12}{'总排放kg/年':>14}{'单位排放g/kWh':>14}")
    for p, d in parks.items():
        mk_w = None if p == "A" else {m: monthly[m][f"{p}_w"] for m in range(12)}
        mk_s = None if p == "B" else {m: monthly[m][f"{p}_pv"] for m in range(12)}
        r = solve_sizing_annual(d["L"] * 1.5, mk_w, mk_s)

        # 加权网购电量
        annual_buy = 0.0
        for m in range(12):
            days = model.DAYS_IN_MONTH[m]
            if mk_w is not None:
                m_w = monthly[m][f"{p}_w"] * r["P_w"]
            else:
                m_w = np.zeros(24)
            if mk_s is not None:
                m_s = monthly[m][f"{p}_pv"] * r["P_pv"]
            else:
                m_s = np.zeros(24)
            op = solve_operation(d["L"] * 1.5, m_w, m_s, r["P_ess"], r["E_ess"],
                                 price_buy=model.TOU_PRICE, c_w=0.0, c_s=0.0)
            annual_buy += op["buy"] * days

        grid_emis = annual_buy * GRID_EMISSION
        ess_carbon = storage_carbon_daily(r["P_ess"], r["E_ess"]) * 365
        total = grid_emis + ess_carbon
        annual_load = d["L"].sum() * 1.5 * 365
        unit = total / annual_load * 1000
        print(f"{p:<6}{annual_buy:>14.0f}{grid_emis:>16.1f}{ess_carbon:>12.1f}"
              f"{total:>14.1f}{unit:>14.1f}")
        rows.append({"场景": "Q3(2) 12月分时电价", "园区": p,
                     "网购电(kWh)": round(annual_buy, 1),
                     "电网排放(kgCO2)": round(grid_emis, 1),
                     "储能隐含碳(kgCO2)": round(ess_carbon, 1),
                     "总排放(kgCO2)": round(total, 1),
                     "单位排放(g/kWh)": round(unit, 1)})

    # ---- 汇总保存 ----
    df = pd.DataFrame(rows)
    path = os.path.join(RESULTS_DIR, "碳排放分析汇总.csv")
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"\n碳排放汇总已保存至 {os.path.basename(path)}")

    # ---- 关键发现 ----
    print("\n" + "=" * 65)
    print("关键发现")
    print("-" * 65)
    # 联合运营减排
    print(f"1. Q2 联合运营较独立合计减少电网排放 "
          f"{indep_grid - joint_grid:.0f} kgCO2/日 "
          f"({(indep_grid - joint_grid) / indep_grid * 100:.1f}%)，"
          f"年化约 {(indep_grid - joint_grid) * 365 / 1000:.1f} 吨")
    # 储能隐含碳 vs 运行减排
    for p, d in parks.items():
        b = analytic_baseline(d["L"], d["W"], d["S"])
        base_emis = b["buy"] * GRID_EMISSION
        s = sweep_storage(d["L"], d["W"], d["S"], (0, 200, 10), (0, 400, 20))
        r_opt = solve_operation(d["L"], d["W"], d["S"], s["P_opt"], s["E_opt"])
        grid_opt = r_opt["buy"] * GRID_EMISSION
        ess_carb = storage_carbon_daily(s["P_opt"], s["E_opt"])
        grid_save = base_emis - grid_opt
        net_save = base_emis - (grid_opt + ess_carb)
        if s["P_opt"] > 0:
            print(f"2. {p} 最优储能 {s['P_opt']:.0f}kW/{s['E_opt']:.0f}kWh: "
                  f"运行减排 {grid_save:.1f} kgCO2/日, "
                  f"隐含碳 {ess_carb:.2f} kgCO2/日, "
                  f"净减排 {net_save:.1f} kgCO2/日")
        else:
            print(f"2. {p} 不配储能: 零隐含碳，最佳碳策略即不配储能")

    # 碳减排成本
    print("3. 碳减排边际成本（元/吨CO2）:")
    for p, d in parks.items():
        s = sweep_storage(d["L"], d["W"], d["S"], (0, 200, 10), (0, 400, 20))
        if s["P_opt"] > 0:
            b = analytic_baseline(d["L"], d["W"], d["S"])
            r_opt = solve_operation(d["L"], d["W"], d["S"], s["P_opt"], s["E_opt"])
            cost_increase = (s["cost_opt"] - b["cost"])  # 注意：最优配置总成本可能比基线高
            carbon_reduction_kg = b["buy"] * GRID_EMISSION - (
                r_opt["buy"] * GRID_EMISSION + storage_carbon_daily(s["P_opt"], s["E_opt"]))
            if carbon_reduction_kg > 0:
                marginal_cost = cost_increase / (carbon_reduction_kg / 1000)  # 元/吨
                print(f"   {p}: {marginal_cost:.0f} 元/吨CO2 "
                      f"({'负成本=减排还省钱' if marginal_cost < 0 else '正成本'})")

    return df


if __name__ == "__main__":
    parks = typical_day_power()
    emission_report(parks)
    print("\n碳排放分析完成。")
