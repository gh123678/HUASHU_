# -*- coding: utf-8 -*-
"""
demand_response.py — 需求响应/可平移负荷分析（加分项）

在运行层 LP 中允许部分负荷（默认 20%）在时间上平移，
验证需求响应对园区运行成本和弃电率的改善效果。

运行：python src/demand_response.py
"""

import os
import numpy as np
import pandas as pd

from model import solve_operation, solve_operation_dr
from solve import analytic_baseline, ESS_DAILY
from utils import check_power_balance, typical_day_power

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
os.makedirs(RESULTS_DIR, exist_ok=True)


def compare_dr(parks, shift_fracs=(0.0, 0.1, 0.2, 0.3)):
    """对比不同可平移负荷比例下的运行效果。

    重点分析 A 园区（中午光伏过剩，负荷平移可替代储能）。
    """
    print("=" * 65)
    print("需求响应分析 —— 可平移负荷对运行成本的影响")
    print("=" * 65)

    rows = []
    HOURS = np.arange(24)

    for frac in shift_fracs:
        print(f"\n{'—' * 50}")
        print(f"可平移负荷比例: {frac:.0%}")
        print(f"{'园区':<4}{'运行成本':>10}{'网购电kWh':>10}{'弃电量kWh':>10}"
              f"{'储能利用':>10}{'峰谷差kW':>12}")

        for p, d in parks.items():
            if frac == 0.0:
                # 无需求响应 = 原始 solve_operation
                r = solve_operation(d["L"], d["W"], d["S"], 0.0, 0.0)
                r["L_shift"] = np.zeros(24)
                r["L_adj"] = d["L"]
            else:
                r = solve_operation_dr(d["L"], d["W"], d["S"], 0.0, 0.0,
                                       max_shift_frac=frac)

            L_orig = d["L"]
            L_adj = r["L_adj"]
            peak_valley_orig = L_orig.max() - L_orig.min()
            peak_valley_adj = L_adj.max() - L_adj.min()

            print(f"{p:<4}{r['cost']:>10.1f}{r['buy']:>10.0f}{r['cur']:>10.0f}"
                  f"{'—':>10}{peak_valley_adj:>12.0f}")

            rows.append({
                "平移比例": f"{frac:.0%}",
                "园区": p,
                "运行成本(元)": round(r["cost"], 1),
                "网购电(kWh)": round(float(r["buy"]), 1),
                "弃电量(kWh)": round(float(r["cur"]), 1),
                "原始峰谷差(kW)": round(float(peak_valley_orig), 1),
                "调整后峰谷差(kW)": round(float(peak_valley_adj), 1),
                "峰谷差缩减": f"{(1 - peak_valley_adj / peak_valley_orig) * 100:.1f}%",
            })

    # ---- 关键场景：A 园区 20% 可平移负荷 + 储能 ----
    print(f"\n{'=' * 65}")
    print("关键场景：A园区 20% 可平移负荷 + 不同储能配置")
    print(f"{'—' * 50}")

    dA = parks["A"]
    b = analytic_baseline(dA["L"], dA["W"], dA["S"])

    # 基线：无DR，无储能
    print(f"\n{'方案':<24}{'运行成本':>10}{'网购电':>10}{'弃电':>10}{'峰谷差':>10}")
    r0 = solve_operation(dA["L"], dA["W"], dA["S"], 0.0, 0.0)
    print(f"{'无DR + 无储能':<24}{r0['cost']:>10.1f}{r0['buy']:>10.0f}"
          f"{r0['cur']:>10.0f}{dA['L'].max()-dA['L'].min():>10.0f}")

    # DR only
    r_dr = solve_operation_dr(dA["L"], dA["W"], dA["S"], 0.0, 0.0, max_shift_frac=0.2)
    L_dr = r_dr["L_adj"]
    cost_dr = r_dr["cost"]
    print(f"{'DR 20% + 无储能':<24}{r_dr['cost']:>10.1f}{r_dr['buy']:>10.0f}"
          f"{r_dr['cur']:>10.0f}{L_dr.max()-L_dr.min():>10.0f}")

    # Storage only (50/100)
    r_s = solve_operation(dA["L"], dA["W"], dA["S"], 50.0, 100.0)
    cost_s = r_s["cost"] + ESS_DAILY(50, 100)
    print(f"{'无DR + 储能50/100':<24}{r_s['cost']:>10.1f}{r_s['buy']:>10.0f}"
          f"{r_s['cur']:>10.0f}{dA['L'].max()-dA['L'].min():>10.0f}")

    # DR + Storage
    r_drs = solve_operation_dr(dA["L"], dA["W"], dA["S"], 50.0, 100.0, max_shift_frac=0.2)
    cost_drs = r_drs["cost"] + ESS_DAILY(50, 100)
    L_drs = r_drs["L_adj"]
    print(f"{'DR 20% + 储能50/100':<24}{r_drs['cost']:>10.1f}{r_drs['buy']:>10.0f}"
          f"{r_drs['cur']:>10.0f}{L_drs.max()-L_drs.min():>10.0f}")

    # ---- 汇总 ----
    print(f"\n{'=' * 65}")
    print("A园区方案对比汇总")
    print(f"{'—' * 50}")
    base_cost = b["cost"]
    print(f"{'方案':<28}{'日总成本':>10}{'较基线':>10}{'弃电降幅':>10}")
    print(f"{'基线（无DR无储能）':<28}{base_cost:>10.1f}{'—':>10}{'—':>10}")

    results = [
        ("DR 20%（无储能）", cost_dr, 0.0, r0["cur"]),
        ("储能 50kW/100kWh（无DR）", cost_s, ESS_DAILY(50, 100), r_s["cur"]),
        ("DR 20% + 储能 50/100", cost_drs, ESS_DAILY(50, 100), r_drs["cur"]),
    ]
    for name, cost, dep, cur in results:
        save = base_cost - cost
        cur_reduc = (r0["cur"] - cur) / r0["cur"] * 100 if r0["cur"] > 0 else 0
        print(f"{name:<28}{cost:>10.1f}{save:>+10.1f}{cur_reduc:>9.1f}%")

    # ---- 保存详细调度表 ----
    df = pd.DataFrame({
        "时段(h)": HOURS,
        "原始负荷(kW)": dA["L"],
        "调整后负荷(kW)": np.round(r_drs["L_adj"], 2),
        "负荷调整量(kW)": np.round(r_drs["L_shift"], 2),
        "光伏消纳(kW)": np.round(r_drs["Su"], 2),
        "储能充电(kW)": np.round(r_drs["ch"], 2),
        "储能放电(kW)": np.round(r_drs["dis"], 2),
        "时段末SOC(kWh)": np.round(r_drs["E"][1:], 2),
        "网购电(kW)": np.round(r_drs["buy_t"], 2),
    })
    path = os.path.join(RESULTS_DIR, "需求响应_A园区_DR20pct_储能50-100.csv")
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"\n调度表已保存至 {os.path.basename(path)}")

    # ---- 储能替代效应：多少储能 = 20% DR？ ----
    print(f"\n{'—' * 50}")
    print("储能替代效应：多大的储能才能达到 20% DR 的弃电削减效果？")
    dr_cur_reduction = r0["cur"] - r_dr["cur"]
    print(f"  DR 20% 弃电削减量: {dr_cur_reduction:.1f} kWh/日")

    # 扫描不同储能容量下 A 园区的弃电量
    best_match = None
    for P in range(0, 301, 10):
        for E in range(0, 601, 10):
            if (P == 0) != (E == 0):
                continue
            r = solve_operation(dA["L"], dA["W"], dA["S"], float(P), float(E))
            cur_reduction = r0["cur"] - r["cur"]
            if abs(cur_reduction - dr_cur_reduction) / dr_cur_reduction < 0.02:
                if best_match is None or P + E < best_match[0] + best_match[1]:
                    best_match = (P, E, cur_reduction)

    if best_match:
        dep_cost = ESS_DAILY(best_match[0], best_match[1])
        print(f"  等效储能配置: {best_match[0]}kW / {best_match[1]}kWh")
        print(f"  等效储能日分摊: {dep_cost:.1f} 元/日")
        print(f"  DR 零成本（仅用户行为调整），储能需投资约 "
              f"{best_match[0]*800 + best_match[1]*1800:.0f} 元")

    # 保存汇总
    summary = pd.DataFrame(rows)
    path2 = os.path.join(RESULTS_DIR, "需求响应_多比例对比.csv")
    summary.to_csv(path2, index=False, encoding="utf-8-sig")
    print(f"\n汇总已保存至 {os.path.basename(path2)}")

    return summary


if __name__ == "__main__":
    parks = typical_day_power()
    compare_dr(parks)
    print("\n需求响应分析完成。")
