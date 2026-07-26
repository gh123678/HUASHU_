# -*- coding: utf-8 -*-
"""
solve.py — 求解与复现脚本（代码手主写）

直接运行 `python src/solve.py` 应复现 docs/总体建模方案.md 第 4 节全部表格
（允许 ±0.5% 数值误差），并通过两项自洽性检查：
  1. 储能容量趋零时 LP 结果退化为解析基线；
  2. 最优解逐时段功率平衡残差 < 1e-6，SOC 轨迹在 [10%, 90%] 内。

push 前必须本地跑通本脚本！
"""

import numpy as np

import model
from model import solve_operation, solve_sizing, solve_sizing_annual
from utils import (
    check_power_balance, load_monthly, typical_day_power,
)


def ESS_DAILY(P, E):
    """储能投资日分摊（动态读 model 常量，便于灵敏度实验修改单价）。"""
    return (model.ESS_P_COST * P + model.ESS_E_COST * E) / (model.ESS_LIFE * 365)


def analytic_baseline(L, W, S, c_w=0.5, c_s=0.4, price_buy=1.0):
    """Q1(1) 解析基线：先消纳光伏(0.4元)再消纳风电(0.5元)，弃电优先弃风电。"""
    L = np.asarray(L, dtype=float)
    W = np.asarray(W, dtype=float)
    S = np.asarray(S, dtype=float)
    Su = np.minimum(S, L)
    rem = L - Su
    Wu = np.minimum(W, rem)
    buy = rem - Wu
    cur = (S - Su).sum() + (W - Wu).sum()
    cost = (Su.sum() * c_s + Wu.sum() * c_w + buy.sum() * price_buy)
    return {
        "buy": float(buy.sum()),
        "cur": float(cur),
        "cost": float(cost),
        "avg": float(cost / L.sum()),
    }


def sweep_storage(L, W, S, Prange, Erange, refine=True, **lp_kwargs):
    """Q1(3)/Q2(2) 储能配置二维网格扫描（方案 6.1 模块 3）。

    每个 (P_ess, E_ess) 解一次 solve_operation，日总成本 = 运行成本 + 储能投资日分摊，
    取最小。粗扫后最优点附近加密（5kW/10kWh）。

    为何不用一步 LP：扫描产出"容量—日总成本"等值线图（论文图证），
    并揭示边际收益递减规律；一步 LP 只给一个点。

    返回
    ----
    dict: P_opt, E_opt, cost_opt, grid(dict: Ps, Es, C 矩阵, 供绘等值线图)
    """
    L, W, S = np.asarray(L, float), np.asarray(W, float), np.asarray(S, float)

    def eval_grid(Ps, Es):
        C = np.full((len(Es), len(Ps)), np.inf)
        for j, P in enumerate(Ps):
            for i, E in enumerate(Es):
                if (P == 0) != (E == 0):
                    continue  # 功率与容量须同零同非零
                if P == 0 and E == 0:
                    r = solve_operation(L, W, S, 0.0, 0.0, **lp_kwargs)
                    C[i, j] = r["cost"]
                else:
                    r = solve_operation(L, W, S, float(P), float(E), **lp_kwargs)
                    C[i, j] = r["cost"] + ESS_DAILY(P, E)
        return C

    Ps = np.arange(Prange[0], Prange[1] + 1e-9, Prange[2])
    Es = np.arange(Erange[0], Erange[1] + 1e-9, Erange[2])
    C = eval_grid(Ps, Es)

    if refine:
        i, j = np.unravel_index(np.nanargmin(C), C.shape)
        P0, E0 = Ps[j], Es[i]
        if P0 > 0 and E0 > 0:
            Ps_f = np.arange(max(0, P0 - Prange[2]), P0 + Prange[2] + 1e-9, 5)
            Es_f = np.arange(max(0, E0 - Erange[2]), E0 + Erange[2] + 1e-9, 10)
            C_f = eval_grid(Ps_f, Es_f)
            i2, j2 = np.unravel_index(np.nanargmin(C_f), C_f.shape)
            if C_f[i2, j2] < C[i, j]:
                Ps, Es, C = Ps_f, Es_f, C_f

    i, j = np.unravel_index(np.nanargmin(C), C.shape)
    return {
        "P_opt": float(Ps[j]),
        "E_opt": float(Es[i]),
        "cost_opt": float(C[i, j]),
        "grid": {"Ps": Ps, "Es": Es, "C": C},
    }


def q1(parks):
    """问题1：独立园区基线 / 50kW-100kWh 评估 / 最优储能扫描。

    复现基准：方案 4.1 / 4.2 / 4.3 节表格。
    解析基线注意：C 园区先消纳光伏(0.4元)再消纳风电(0.5元)，弃电优先弃风电。
    """
    print("=" * 60)
    print("问题1：各园区独立运营")
    print("-" * 60)
    print("【1(1) 不配储能基线（解析）】")
    print(f"{'园区':<4}{'购电量kWh':>12}{'弃电量kWh':>12}{'总成本元/日':>14}{'单位成本':>10}")
    baseline = {}
    for p, d in parks.items():
        b = analytic_baseline(d["L"], d["W"], d["S"])
        baseline[p] = b
        print(f"{p:<4}{b['buy']:>12.0f}{b['cur']:>12.0f}{b['cost']:>14.1f}{b['avg']:>10.3f}")

    print("\n【1(2) 配 50kW/100kWh（LP）】")
    print(f"{'园区':<4}{'运行成本':>12}{'较基线降幅':>12}{'储能日分摊':>12}{'净收益':>10}")
    dep = ESS_DAILY(50, 100)
    for p, d in parks.items():
        r = solve_operation(d["L"], d["W"], d["S"], 50.0, 100.0)
        check_power_balance(r, d["L"], 50.0, 100.0)
        drop = baseline[p]["cost"] - r["cost"]
        print(f"{p:<4}{r['cost']:>12.1f}{drop:>12.1f}{dep:>12.1f}{drop - dep:>10.1f}")

    print("\n【1(3) 最优储能配置（网格扫描+加密）】")
    print(f"{'园区':<4}{'P_opt(kW)':>12}{'E_opt(kWh)':>12}{'日总成本':>12}{'较基线节省':>12}")
    sweeps = {}
    for p, d in parks.items():
        s = sweep_storage(d["L"], d["W"], d["S"], (0, 200, 10), (0, 400, 20))
        sweeps[p] = s
        save = baseline[p]["cost"] - s["cost_opt"]
        print(f"{p:<4}{s['P_opt']:>12.0f}{s['E_opt']:>12.0f}{s['cost_opt']:>12.1f}{save:>12.1f}")
    return baseline, sweeps


def q2(parks):
    """问题2：三园区功率逐时叠加后联合运营，对比独立合计。

    复现基准：方案 4.4 节表格（联合后最优储能为 0 是核心结论）。
    """
    print("\n" + "=" * 60)
    print("问题2：联合园区运营")
    print("-" * 60)
    L = sum(d["L"] for d in parks.values())
    W = sum(d["W"] for d in parks.values())
    S = sum(d["S"] for d in parks.values())

    b = analytic_baseline(L, W, S)
    print(f"【2(1) 联合无储能】购电量 {b['buy']:.0f} kWh, 弃电量 {b['cur']:.0f} kWh, "
          f"日成本 {b['cost']:.1f} 元, 单位成本 {b['avg']:.3f} 元/kWh")

    s = sweep_storage(L, W, S, (0, 200, 10), (0, 400, 20))
    print(f"【2(2) 联合最优储能】P={s['P_opt']:.0f} kW, E={s['E_opt']:.0f} kWh, "
          f"日总成本 {s['cost_opt']:.1f} 元")
    return {"L": L, "W": W, "S": S}, b, s


def q3(parks):
    """问题3：负荷×1.5 的风光储协调配置。

    3(1) 固定电价单 LP（复现 4.5）；3(2) 12 月耦合 + 分时电价（复现 4.6）。
    注意：Q3 风光为自建资产，运行成本不计电量费。
    """
    print("\n" + "=" * 60)
    print("问题3：风光储协调配置（负荷×1.5）")
    print("-" * 60)
    from utils import load_typical_day
    pu = load_typical_day()

    print("【3(1) 固定电价 1 元/kWh】")
    print(f"{'园区':<6}{'风电kW':>10}{'光伏kW':>10}{'储能kW':>10}{'储能kWh':>10}{'日总成本':>12}")
    res31 = {}
    pu_map = {
        "A": (None, pu["A_pv"]),
        "B": (pu["B_w"], None),
        "C": (pu["C_w"], pu["C_pv"]),
    }
    for p, d in parks.items():
        r = solve_sizing(d["L"] * 1.5, *pu_map[p], price_buy=1.0)
        res31[p] = r
        print(f"{p:<6}{r['P_w']:>10.0f}{r['P_pv']:>10.0f}{r['P_ess']:>10.0f}"
              f"{r['E_ess']:>10.0f}{r['cost']:>12.1f}")

    # 联合园区：风光 pu 按原装机比例加权混合（风 1000:500=2:1，光 750:600=5:4）
    L_j = sum(d["L"] for d in parks.values()) * 1.5
    pu_w_j = (1000 * pu["B_w"] + 500 * pu["C_w"]) / 1500
    pu_s_j = (750 * pu["A_pv"] + 600 * pu["C_pv"]) / 1350
    r = solve_sizing(L_j, pu_w_j, pu_s_j, price_buy=1.0)
    res31["联合"] = r
    print(f"{'联合':<6}{r['P_w']:>10.0f}{r['P_pv']:>10.0f}{r['P_ess']:>10.0f}"
          f"{r['E_ess']:>10.0f}{r['cost']:>12.1f}")

    print("\n【3(2) 12 月耦合 + 分时电价（独立运营）】")
    print(f"{'园区':<6}{'风电kW':>10}{'光伏kW':>10}{'储能kW':>10}{'储能kWh':>10}{'加权日总成本':>14}")
    monthly = load_monthly()
    res32 = {}
    for p, d in parks.items():
        mk_w = None if p == "A" else {m: monthly[m][f"{p}_w"] for m in range(12)}
        mk_s = None if p == "B" else {m: monthly[m][f"{p}_pv"] for m in range(12)}
        r = solve_sizing_annual(d["L"] * 1.5, mk_w, mk_s)
        res32[p] = r
        print(f"{p:<6}{r['P_w']:>10.0f}{r['P_pv']:>10.0f}{r['P_ess']:>10.0f}"
              f"{r['E_ess']:>10.0f}{r['cost']:>14.1f}")
    return res31, res32


def sensitivity(parks):
    """灵敏度分析三组实验（方案 6.3，加分项）。"""
    print("\n" + "=" * 60)
    print("灵敏度分析")
    print("-" * 60)

    print("【实验1：储能能量单价 1800 → 1440 / 900 元/kWh，重跑 Q1(3)】")
    orig = model.ESS_E_COST
    for price in (1800, 1440, 900):
        model.ESS_E_COST = price
        line = f"  单价 {price:>5} 元/kWh: "
        for p, d in parks.items():
            s = sweep_storage(d["L"], d["W"], d["S"], (0, 200, 10), (0, 400, 20),
                              refine=False)
            line += f"{p}={s['P_opt']:.0f}/{s['E_opt']:.0f}  "
        print(line)
    model.ESS_E_COST = orig

    print("【实验2：网购电价 ±20% 对 Q1(3) 最优容量的影响】")
    for factor in (0.8, 1.0, 1.2):
        line = f"  电价 {factor:.1f}×: "
        for p, d in parks.items():
            s = sweep_storage(d["L"], d["W"], d["S"], (0, 200, 10), (0, 400, 20),
                              refine=False, price_buy=1.0 * factor)
            line += f"{p}={s['P_opt']:.0f}/{s['E_opt']:.0f}  "
        print(line)

    print("【实验3：投资回报期 5 → 8 年对 Q3(1) 装机的影响】")
    from utils import load_typical_day
    pu = load_typical_day()
    orig_payback = model.INV_PAYBACK
    pu_map = {"A": (None, pu["A_pv"]), "B": (pu["B_w"], None), "C": (pu["C_w"], pu["C_pv"])}
    for years in (5, 8):
        model.INV_PAYBACK = years
        line = f"  回报期 {years} 年: "
        for p, d in parks.items():
            r = solve_sizing(d["L"] * 1.5, *pu_map[p], price_buy=1.0)
            line += f"{p} 风{r['P_w']:.0f}/光{r['P_pv']:.0f}/储{r['P_ess']:.0f}-{r['E_ess']:.0f}  "
        print(line)
    model.INV_PAYBACK = orig_payback


def degeneration_check(parks):
    """自洽性检查1：储能容量趋零时 LP 结果退化为解析基线。"""
    print("\n【退化校验：LP(E_ess→0) ≈ 解析基线】")
    ok = True
    for p, d in parks.items():
        b = analytic_baseline(d["L"], d["W"], d["S"])
        r = solve_operation(d["L"], d["W"], d["S"], 1e-4, 1e-3)
        diff = abs(r["cost"] - b["cost"])
        status = "OK" if diff < 0.5 else "FAIL"
        ok &= diff < 0.5
        print(f"  {p}: LP {r['cost']:.1f} vs 解析 {b['cost']:.1f}, 差 {diff:.3f} [{status}]")
    return ok


if __name__ == "__main__":
    parks = typical_day_power()
    degeneration_check(parks)
    q1(parks)
    q2(parks)
    q3(parks)
    sensitivity(parks)
    print("\n全部求解完成，请与 docs/总体建模方案.md 第 4 节对表（±0.5%）。")
