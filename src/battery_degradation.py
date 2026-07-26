# -*- coding: utf-8 -*-
"""
battery_degradation.py — 电池衰减建模（加分项）

分析储能系统在全生命周期内的衰减对经济性的影响：
  1. 循环衰减：每充放电一次，电池容量微量下降
  2. 日历衰减：时间推移导致容量自然衰退

在运行层 LP 中加入衰减边际成本 λ_deg (元/kWh 吞吐量)，
将电池投资转化为"按使用量付费"的边际成本。

运行：python src/battery_degradation.py
"""

import os
import numpy as np
import pandas as pd

from model import (solve_operation, solve_operation_degradation,
                    degradation_rate, ESS_P_COST, ESS_E_COST, ESS_LIFE)
from solve import analytic_baseline, ESS_DAILY, sweep_storage
from utils import typical_day_power

RESULTS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "results")
os.makedirs(RESULTS_DIR, exist_ok=True)


def compare_degradation(parks):
    """对比有/无衰减成本的调度差异。"""
    print("=" * 65)
    print("电池衰减分析 —— 循环衰减对调度和经济性的影响")
    print("=" * 65)

    rows = []
    P, E = 50.0, 100.0

    for cycle_life in [10000, 6000, 4000, 2000]:
        lam = degradation_rate(P, E, cycle_life)
        print(f"\n{'—' * 50}")
        print(f"循环寿命: {cycle_life} 次 | λ_deg = {lam:.4f} 元/kWh")
        print(f"{'园区':<4}{'调度成本':>10}{'衰减成本':>10}{'总成本':>10}"
              f"{'吞吐量kWh':>12}{'网购电':>10}{'弃电':>8}")

        for p, d in parks.items():
            r = solve_operation_degradation(d["L"], d["W"], d["S"],
                                             P, E, cycle_life=cycle_life)
            op_cost = r["cost"] - r["degradation_cost"]
            total = r["cost"]
            print(f"{p:<4}{op_cost:>10.1f}{r['degradation_cost']:>10.1f}{total:>10.1f}"
                  f"{r['throughput']:>12.0f}{r['buy']:>10.0f}{r['cur']:>8.0f}")

            # 对比无衰减的情况
            r0 = solve_operation(d["L"], d["W"], d["S"], P, E)
            rows.append({
                "循环寿命": cycle_life,
                "λ_deg(元/kWh)": round(lam, 4),
                "园区": p,
                "调度成本(不含衰减)": round(float(op_cost), 1),
                "衰减成本(元)": round(float(r["degradation_cost"]), 1),
                "含衰减总成本(元)": round(float(total), 1),
                "无衰减总成本(元)": round(float(r0["cost"]), 1),
                "吞吐量(kWh)": round(float(r["throughput"]), 1),
                "网购电变化(kWh)": round(float(r["buy"] - r0["buy"]), 1),
            })

    df = pd.DataFrame(rows)
    path = os.path.join(RESULTS_DIR, "电池衰减_循环寿命对比.csv")
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"\n结果已保存至 {os.path.basename(path)}")
    return df


def marginal_cost_analysis(parks):
    """衰减成本占总成本的比例 vs 储能配置。"""
    print(f"\n{'=' * 65}")
    print("衰减边际成本占比 —— 不同储能配置下的衰减成本分析")
    print(f"{'—' * 50}")

    rows = []
    dA = parks["A"]
    configs = [(0, 0), (25, 50), (50, 100), (100, 200), (150, 300)]

    print(f"{'配置':>14}{'调度成本':>10}{'衰减成本':>10}{'总成本':>10}{'衰减占比':>10}")
    for P, E in configs:
        if P == 0:
            r0 = solve_operation(dA["L"], dA["W"], dA["S"], 0.0, 0.0)
            print(f"{'0/0 (无储能)':>14}{r0['cost']:>10.1f}{0:>10.1f}{r0['cost']:>10.1f}"
                  f"{'—':>10}")
            rows.append({"P(kW)": P, "E(kWh)": E,
                         "调度成本(元)": round(float(r0["cost"]), 1),
                         "衰减成本(元)": 0.0,
                         "总成本(元)": round(float(r0["cost"]), 1),
                         "衰减占比": "0%"})
            continue

        r = solve_operation_degradation(dA["L"], dA["W"], dA["S"],
                                         float(P), float(E))
        op_cost = r["cost"] - r["degradation_cost"]
        total = r["cost"] + ESS_DAILY(P, E)
        deg_ratio = r["degradation_cost"] / total * 100
        print(f"{f'{P}/{E}':>14}{op_cost:>10.1f}{r['degradation_cost']:>10.1f}"
              f"{total:>10.1f}{deg_ratio:>9.1f}%")
        rows.append({"P(kW)": P, "E(kWh)": E,
                     "调度成本(元)": round(float(op_cost), 1),
                     "衰减成本(元)": round(float(r["degradation_cost"]), 1),
                     "总成本(含储能日分摊)(元)": round(float(total), 1),
                     "衰减占比": f"{deg_ratio:.1f}%",
                     "λ_deg(元/kWh)": round(r["lambda_deg"], 4)})

    df = pd.DataFrame(rows)
    path = os.path.join(RESULTS_DIR, "电池衰减_配置对比.csv")
    df.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"\n结果已保存至 {os.path.basename(path)}")
    return df


def calendar_aging_analysis(parks):
    """日历衰减分析：容量随年限线性衰减对经济性的影响。

    典型 LFP 日历衰减：首年 3%，后续每年约 1%。
    按 10 年寿命计算平均可用容量。

    如果每年容量衰减 a%，则第 k 年剩余容量 = (1 - a)^k。
    年均可用容量 ≈ E0 * (1 - total_loss / 2)，简化处理。
    """
    print(f"\n{'=' * 65}")
    print("日历衰减 —— 容量逐年衰减对全生命周期经济性的影响")
    print(f"{'—' * 50}")

    # LFP 典型参数
    first_year_loss = 0.03   # 首年 3%
    annual_loss = 0.01       # 后续每年 1%
    cycle_life = 6000

    # 计算 10 年内各年剩余容量
    years = np.arange(1, 11)
    capacity = np.ones(10)
    capacity[0] = 1.0 - first_year_loss
    for y in range(1, 10):
        capacity[y] = capacity[y - 1] * (1.0 - annual_loss)

    avg_capacity_factor = capacity.mean()
    print(f"  10 年平均可用容量系数: {avg_capacity_factor:.3f}")
    print(f"  第 10 年末剩余容量系数: {capacity[-1]:.3f}")

    # 对 A 园区的储能方案做比较
    dA = parks["A"]
    P, E = 50.0, 100.0
    r_full = solve_operation_degradation(dA["L"], dA["W"], dA["S"], P, E,
                                          cycle_life=cycle_life)
    E_avg = E * avg_capacity_factor
    r_avg = solve_operation_degradation(dA["L"], dA["W"], dA["S"], P, E_avg,
                                         cycle_life=cycle_life)

    print(f"\n  A园区 50kW/100kWh 储能:")
    print(f"    额定容量 100kWh — 含衰减调度成本: {r_full['cost']:.1f} 元/日")
    print(f"    年均可用 {E_avg:.0f}kWh — 含衰减调度成本: {r_avg['cost']:.1f} 元/日")

    dep_full = ESS_DAILY(P, E)
    dep_avg = ESS_DAILY(P, E_avg)
    total_full = r_full["cost"] + dep_full
    total_avg = r_avg["cost"] + dep_avg

    print(f"    额定容量 — 含储能分摊总成本: {total_full:.1f} 元/日")
    print(f"    年均可用 — 含储能分摊总成本: {total_avg:.1f} 元/日")

    # 保存容量衰减曲线
    df_cap = pd.DataFrame({
        "年份": years,
        "容量系数": np.round(capacity, 4),
        "可用容量(kWh)": np.round(capacity * E, 1),
    })
    path = os.path.join(RESULTS_DIR, "电池衰减_日历衰减曲线.csv")
    df_cap.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"\n  日历衰减曲线已保存至 {os.path.basename(path)}")

    return capacity


def main():
    parks = typical_day_power()

    # 1. 不同循环寿命下的衰减成本对比
    compare_degradation(parks)

    # 2. A园区衰减成本 vs 储能配置
    marginal_cost_analysis(parks)

    # 3. 日历衰减
    calendar_aging_analysis(parks)

    # 4. 关键发现
    print(f"\n{'=' * 65}")
    print("关键发现")
    print(f"{'—' * 50}")

    P, E = 50.0, 100.0
    lam_default = degradation_rate(P, E, 6000)
    dep = ESS_DAILY(P, E)
    print(f"1. 标准 LFP (6000 次循环): λ_deg = {lam_default:.3f} 元/kWh")
    print(f"   50kW/100kWh 平均日吞吐量约 200-300 kWh，")
    print(f"   日衰减成本约 {lam_default * 250:.1f} 元，占储能日分摊 {dep:.1f} 元的 "
          f"{lam_default * 250 / dep * 100:.0f}%")
    print(f"2. 高质量电池 (10000 次): λ_deg = {degradation_rate(P, E, 10000):.3f} 元/kWh")
    print(f"   衰减成本降低 {(1 - degradation_rate(P, E, 10000)/lam_default) * 100:.0f}%")
    print(f"3. 储能越大，衰减边际成本越低（固定成本摊到更多 kWh 吞吐量）")
    print(f"4. 日历衰减使年均可用容量降约 {(1 - 0.91) * 100:.0f}%，"
          f"建议按年均可用容量做储能配置")

    print("\n电池衰减分析完成。")


if __name__ == "__main__":
    main()
