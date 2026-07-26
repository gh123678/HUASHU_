# -*- coding: utf-8 -*-
"""
plots.py — 论文图表生成（方案 6.1 绘图清单）

全部中文标注、150dpi，输出至 docs/figures/。
运行：python src/plots.py
"""

import os

import numpy as np
import matplotlib.pyplot as plt

import model
from model import TOU_PRICE, solve_operation
from solve import ESS_DAILY, analytic_baseline, sweep_storage
from utils import FIG_DIR, load_monthly, load_typical_day, typical_day_power

DPI = 150
HOURS = np.arange(24)
PARK_NAME = {"A": "园区A", "B": "园区B", "C": "园区C"}


def _save(fig, name):
    path = os.path.join(FIG_DIR, name)
    fig.savefig(path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)
    print("saved:", name)


def fig1_load_curves(parks):
    """图1：三园区典型日负荷曲线（题目图2复现）。"""
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for p, d in parks.items():
        ax.plot(HOURS, d["L"], marker="o", ms=3, label=PARK_NAME[p])
    ax.set_xlabel("时间（h）")
    ax.set_ylabel("功率（kW）")
    ax.set_title("三园区典型日负荷功率曲线（数据来源：附件1）")
    ax.legend()
    ax.grid(alpha=0.3)
    _save(fig, "fig1_三园区负荷曲线.png")


def _stack_dispatch(ax, r, L, title):
    """逐时功率堆叠图：供应侧 风/光/放电/购电，需求侧 负荷线+充电。"""
    ax.bar(HOURS, r["Wu"], label="风电消纳", color="#4C9F70")
    ax.bar(HOURS, r["Su"], bottom=r["Wu"], label="光伏消纳", color="#F2C14E")
    base = r["Wu"] + r["Su"]
    ax.bar(HOURS, r["dis"], bottom=base, label="储能放电", color="#E4572E")
    ax.bar(HOURS, r["buy_t"], bottom=base + r["dis"], label="网购电", color="#7A7A7A")
    ax.bar(HOURS, -r["ch"], label="储能充电", color="#2E86AB")
    ax.plot(HOURS, L, color="k", lw=1.5, label="负荷")
    ax.axhline(0, color="k", lw=0.5)
    ax.set_xlabel("时间（h）")
    ax.set_ylabel("功率（kW）")
    ax.set_title(title)
    ax.legend(fontsize=8, ncol=3)
    ax.grid(alpha=0.3)


def fig2_q12_dispatch(parks):
    """图2：Q1(2) 各园区 50kW/100kWh 逐时功率堆叠 + SOC 轨迹（3 子图）。"""
    fig, axes = plt.subplots(3, 2, figsize=(12, 11))
    for i, (p, d) in enumerate(parks.items()):
        r = solve_operation(d["L"], d["W"], d["S"], 50.0, 100.0)
        _stack_dispatch(axes[i, 0], r, d["L"],
                        f"{PARK_NAME[p]} 逐时功率平衡（50kW/100kWh）")
        ax2 = axes[i, 1]
        ax2.plot(np.arange(25), r["E"], marker="o", ms=3, color="#2E86AB")
        ax2.axhline(90, ls="--", c="r", lw=1, label="SOC 上限 90%")
        ax2.axhline(10, ls="--", c="r", lw=1, label="SOC 下限 10%")
        ax2.set_xlabel("时段")
        ax2.set_ylabel("储能电量（kWh）")
        ax2.set_title(f"{PARK_NAME[p]} 储能 SOC 轨迹")
        ax2.legend(fontsize=8)
        ax2.grid(alpha=0.3)
    fig.tight_layout()
    _save(fig, "fig2_Q12_各园区调度与SOC.png")


def fig3_q13_contour(parks):
    """图3：Q1(3) 储能容量—日总成本等值线图（每园区 1 张）。"""
    for p, d in parks.items():
        s = sweep_storage(d["L"], d["W"], d["S"], (0, 200, 10), (0, 400, 20),
                          refine=False)
        g = s["grid"]
        C = np.where(np.isfinite(g["C"]), g["C"], np.nan)
        fig, ax = plt.subplots(figsize=(7, 5.5))
        cs = ax.contourf(g["Ps"], g["Es"], C, levels=20, cmap="viridis")
        fig.colorbar(cs, label="日总成本（元/日）")
        ax.plot(50, 100, "rs", ms=9, label="原方案 50kW/100kWh")
        ax.plot(s["P_opt"], s["E_opt"], "w*", ms=15,
                label=f"最优 {s['P_opt']:.0f}kW/{s['E_opt']:.0f}kWh")
        ax.set_xlabel("储能功率（kW）")
        ax.set_ylabel("储能容量（kWh）")
        ax.set_title(f"{PARK_NAME[p]} 储能配置—日总成本等值线图")
        ax.legend()
        _save(fig, f"fig3_Q13_等值线_{p}.png")


def fig4_q2_compare(parks, joint):
    """图4：Q2 独立 vs 联合——逐时净负荷对比 + 指标柱状图。"""
    L, W, S = joint["L"], joint["W"], joint["S"]
    net_joint = L - W - S
    net_indep = sum(d["L"] - d["W"] - d["S"] for d in parks.values())

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))
    ax1.plot(HOURS, net_indep, label="独立运营净负荷叠加", marker="o", ms=3)
    ax1.plot(HOURS, net_joint, label="联合园区净负荷", marker="s", ms=3)
    ax1.axhline(0, color="k", lw=0.5)
    ax1.set_xlabel("时间（h）")
    ax1.set_ylabel("净负荷功率（kW）")
    ax1.set_title("独立 vs 联合：逐时净负荷对比")
    ax1.legend()
    ax1.grid(alpha=0.3)

    b_i = [analytic_baseline(d["L"], d["W"], d["S"]) for d in parks.values()]
    b_j = analytic_baseline(L, W, S)
    labels = ["购电量（kWh）", "弃电量（kWh）", "日成本（百元）"]
    indep = [sum(b["buy"] for b in b_i), sum(b["cur"] for b in b_i),
             sum(b["cost"] for b in b_i) / 100]
    joint_v = [b_j["buy"], b_j["cur"], b_j["cost"] / 100]
    x = np.arange(3)
    ax2.bar(x - 0.2, indep, 0.4, label="独立运营合计")
    ax2.bar(x + 0.2, joint_v, 0.4, label="联合运营")
    for xi, (a, b) in enumerate(zip(indep, joint_v)):
        ax2.text(xi - 0.2, a, f"{a:.0f}", ha="center", va="bottom", fontsize=8)
        ax2.text(xi + 0.2, b, f"{b:.0f}", ha="center", va="bottom", fontsize=8)
    ax2.set_xticks(x)
    ax2.set_xticklabels(labels)
    ax2.set_title("独立 vs 联合：关键指标对比")
    ax2.legend()
    ax2.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    _save(fig, "fig4_Q2_独立vs联合.png")


def fig5_q32_typical_month(parks):
    """图5：Q3(2) 典型月（2 月与 8 月）逐时调度堆叠 + SOC（以园区C为例）。"""
    monthly = load_monthly()
    mk_w = {m: monthly[m]["C_w"] for m in range(12)}
    mk_s = {m: monthly[m]["C_pv"] for m in range(12)}
    r = model.solve_sizing_annual(parks["C"]["L"] * 1.5, mk_w, mk_s)
    P_w, P_pv, P_ess, E_ess = r["P_w"], r["P_pv"], r["P_ess"], r["E_ess"]

    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    for i, m in enumerate((1, 7)):  # 2 月、8 月（0 基）
        W = monthly[m]["C_w"] * P_w
        S = monthly[m]["C_pv"] * P_pv
        rr = solve_operation(parks["C"]["L"] * 1.5, W, S, P_ess, E_ess,
                             price_buy=TOU_PRICE, c_w=0.0, c_s=0.0)
        _stack_dispatch(axes[i, 0], rr, parks["C"]["L"] * 1.5,
                        f"园区C {m + 1} 月典型日调度（Q3(2) 配置）")
        ax2 = axes[i, 1]
        ax2.plot(np.arange(25), rr["E"], marker="o", ms=3, color="#2E86AB")
        ax2.axhline(0.9 * E_ess, ls="--", c="r", lw=1)
        ax2.axhline(0.1 * E_ess, ls="--", c="r", lw=1)
        ax2.set_xlabel("时段")
        ax2.set_ylabel("储能电量（kWh）")
        ax2.set_title(f"园区C {m + 1} 月 SOC 轨迹")
        ax2.grid(alpha=0.3)
    fig.tight_layout()
    _save(fig, "fig5_Q32_典型月调度_C.png")


def fig6_sensitivity(parks):
    """图6：灵敏度分析——储能能量单价 vs Q1(3) 最优配置与节省额。"""
    prices = [1800, 1620, 1440, 1260, 1080, 900, 720]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.5))
    for p, d in parks.items():
        Es, saves = [], []
        base = analytic_baseline(d["L"], d["W"], d["S"])["cost"]
        for pr in prices:
            model.ESS_E_COST = pr
            s = sweep_storage(d["L"], d["W"], d["S"], (0, 200, 10), (0, 400, 20),
                              refine=False)
            Es.append(s["E_opt"])
            saves.append(base - s["cost_opt"])
        ax1.plot(prices, Es, marker="o", ms=4, label=PARK_NAME[p])
        ax2.plot(prices, saves, marker="o", ms=4, label=PARK_NAME[p])
    model.ESS_E_COST = 1800
    ax1.set_xlabel("储能能量单价（元/kWh）")
    ax1.set_ylabel("最优储能容量（kWh）")
    ax1.set_title("电池价格 vs 最优储能容量")
    ax1.legend()
    ax1.grid(alpha=0.3)
    ax2.set_xlabel("储能能量单价（元/kWh）")
    ax2.set_ylabel("较基线日节省（元/日）")
    ax2.set_title("电池价格 vs 储能经济效益")
    ax2.axhline(0, color="r", ls="--", lw=1)
    ax2.legend()
    ax2.grid(alpha=0.3)
    fig.tight_layout()
    _save(fig, "fig6_灵敏度_电池价格.png")


if __name__ == "__main__":
    parks = typical_day_power()
    fig1_load_curves(parks)
    fig2_q12_dispatch(parks)
    fig3_q13_contour(parks)
    joint = {k: sum(d[k] for d in parks.values()) for k in ("L", "W", "S")}
    fig4_q2_compare(parks, joint)
    fig5_q32_typical_month(parks)
    fig6_sensitivity(parks)
    print("全部图表已生成至 docs/figures/")
