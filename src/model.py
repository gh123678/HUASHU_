# -*- coding: utf-8 -*-
"""
model.py — 核心 LP 模型（代码手主写）

全题共用一个线性规划核心模型，三问只是边界条件和决策变量层级不同。
建模约定与符号定义见 docs/总体建模方案.md 第 2 节，改动前必须全队讨论。

求解器统一用 scipy.optimize.linprog(method='highs')，全程不需要智能算法。
"""

import numpy as np
from scipy.optimize import linprog

# ---- 全局常量（题目给定，勿改） ----
ETA = 0.95            # 储能充/放电效率
SOC_LO, SOC_HI = 0.1, 0.9   # SOC 允许范围
ESS_P_COST = 800      # 储能功率单价 元/kW
ESS_E_COST = 1800     # 储能能量单价 元/kWh
ESS_LIFE = 10         # 储能寿命 年
WIND_COST = 3000      # Q3 风电配置成本 元/kW
PV_COST = 2500        # Q3 光伏配置成本 元/kW
INV_PAYBACK = 5       # Q3 风光投资回报期 年
DAYS_IN_MONTH = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]  # Q3(2) 月天数加权

T = 24  # 时段数

# 分时电价（表1）：7:00-22:00 为 1 元，其余 0.4 元
TOU_PRICE = np.array([0.4] * 7 + [1.0] * 15 + [0.4] * 2)


def _price_vec(price_buy):
    p = np.asarray(price_buy, dtype=float)
    if p.ndim == 0:
        p = np.full(T, float(p))
    assert p.shape == (T,), "price_buy 必须是标量或 24 维向量"
    return p


def solve_operation(L, W, S, P_ess, E_ess, price_buy=1.0, c_w=0.5, c_s=0.4):
    """运行层 LP：给定装机与储能，求单日最优调度（Q1/Q2 主求解器）。

    参数
    ----
    L, W, S : (24,) 负荷 / 风电 / 光伏功率数组（kW），无该电源时传全零数组
    P_ess, E_ess : 储能额定功率(kW) / 容量(kWh)，固定值
    price_buy : 网购电价，标量（固定电价）或 (24,) 向量（分时电价）
    c_w, c_s : 风/光电量费 元/kWh（Q1/Q2 向第三方购电；Q3 自建资产传 0）

    返回
    ----
    dict: cost(运行成本), buy, cur(弃电), ch, dis, E(SOC轨迹,25点), Wu, Su, buy_t

    实现要点（方案 6.1 模块 2）
    ----
    - 变量排布: buy(24) ch(24) dis(24) Wuse(24) Suse(24) E(25)，共 145 个
    - 约束: 功率平衡 24 条 + SOC 递推 24 条 + 循环约束 E[24]=E[0] 1 条
    - SOC 边界: SOC_LO*E_ess <= E_t <= SOC_HI*E_ess
    - 无需充放电互斥 0-1 变量：eta<1 时同时充放只会增成本，最优解自动互斥
    """
    L = np.asarray(L, dtype=float)
    W = np.asarray(W, dtype=float)
    S = np.asarray(S, dtype=float)
    price = _price_vec(price_buy)

    n = 5 * T + (T + 1)
    i_buy, i_ch, i_dis, i_wu, i_su, i_e = 0, T, 2 * T, 3 * T, 4 * T, 5 * T

    # 目标：min Σ [price_t·buy_t + c_w·Wuse_t + c_s·Suse_t]
    c = np.zeros(n)
    c[i_buy:i_ch] = price
    c[i_wu:i_su] = c_w
    c[i_su:i_e] = c_s

    A_eq, b_eq = [], []

    # 功率平衡: Wuse_t + Suse_t + dis_t + buy_t - ch_t = L_t
    for t in range(T):
        row = np.zeros(n)
        row[i_buy + t] = 1.0
        row[i_ch + t] = -1.0
        row[i_dis + t] = 1.0
        row[i_wu + t] = 1.0
        row[i_su + t] = 1.0
        A_eq.append(row)
        b_eq.append(L[t])

    # SOC 递推: E_{t+1} - E_t - η·ch_t + dis_t/η = 0
    for t in range(T):
        row = np.zeros(n)
        row[i_e + t + 1] = 1.0
        row[i_e + t] = -1.0
        row[i_ch + t] = -ETA
        row[i_dis + t] = 1.0 / ETA
        A_eq.append(row)
        b_eq.append(0.0)

    # 循环约束: E_24 = E_0
    row = np.zeros(n)
    row[i_e + T] = 1.0
    row[i_e] = -1.0
    A_eq.append(row)
    b_eq.append(0.0)

    bounds = (
        [(0, None)] * T                              # buy
        + [(0, P_ess)] * T                           # ch
        + [(0, P_ess)] * T                           # dis
        + [(0, W[t]) for t in range(T)]              # Wuse
        + [(0, S[t]) for t in range(T)]              # Suse
        + [(SOC_LO * E_ess, SOC_HI * E_ess)] * (T + 1)  # E
    )

    res = linprog(c, A_eq=np.array(A_eq), b_eq=np.array(b_eq),
                  bounds=bounds, method="highs")
    if not res.success:
        raise RuntimeError(f"运行层 LP 求解失败: {res.message}")

    x = res.x
    buy_t = x[i_buy:i_ch]
    Wu = x[i_wu:i_su]
    Su = x[i_su:i_e]
    return {
        "cost": float(res.fun),
        "buy": float(buy_t.sum()),
        "cur": float((W - Wu).sum() + (S - Su).sum()),
        "ch": x[i_ch:i_dis],
        "dis": x[i_dis:i_wu],
        "E": x[i_e:i_e + T + 1],
        "Wu": Wu,
        "Su": Su,
        "buy_t": buy_t,
    }


def solve_sizing(L, pu_w, pu_s, price_buy):
    """容量层 LP：风光储容量直接作为决策变量（Q3(1) 单场景）。

    参数
    ----
    L : (24,) 负荷（Q3 已 ×1.5）
    pu_w, pu_s : (24,) 风/光出力标幺值，无该电源传 None（保持原电源类型）
    price_buy : 标量或 (24,) 分时电价

    返回
    ----
    dict: P_w, P_pv, P_ess, E_ess(最优容量), cost(日总成本, 含投资分摊)

    实现要点：Wuse_t <= pu_w[t]*P_w、E_t <= SOC_HI*E_ess 等约束关于容量均线性，
    目标 = 运行成本 + 储能分摊/10/365 + 风光分摊/5/365，单 LP 即全局最优。
    Q3 风光为自建资产，运行成本中不计 0.5/0.4 电量费（方案第 5 节约定 1）。
    """
    L = np.asarray(L, dtype=float)
    price = _price_vec(price_buy)

    # 变量: buy(24) ch(24) dis(24) Wuse(24) Suse(24) E(25) P_w P_pv P_ess E_ess
    n = 5 * T + (T + 1) + 4
    i_buy, i_ch, i_dis, i_wu, i_su, i_e = 0, T, 2 * T, 3 * T, 4 * T, 5 * T
    i_pw, i_ppv, i_pess, i_eess = n - 4, n - 3, n - 2, n - 1

    c = np.zeros(n)
    c[i_buy:i_ch] = price
    c[i_pw] = WIND_COST / (INV_PAYBACK * 365)
    c[i_ppv] = PV_COST / (INV_PAYBACK * 365)
    c[i_pess] = ESS_P_COST / (ESS_LIFE * 365)
    c[i_eess] = ESS_E_COST / (ESS_LIFE * 365)

    A_eq, b_eq = [], []

    # 功率平衡
    for t in range(T):
        row = np.zeros(n)
        row[i_buy + t] = 1.0
        row[i_ch + t] = -1.0
        row[i_dis + t] = 1.0
        row[i_wu + t] = 1.0
        row[i_su + t] = 1.0
        A_eq.append(row)
        b_eq.append(L[t])

    # SOC 递推
    for t in range(T):
        row = np.zeros(n)
        row[i_e + t + 1] = 1.0
        row[i_e + t] = -1.0
        row[i_ch + t] = -ETA
        row[i_dis + t] = 1.0 / ETA
        A_eq.append(row)
        b_eq.append(0.0)

    # 循环约束
    row = np.zeros(n)
    row[i_e + T] = 1.0
    row[i_e] = -1.0
    A_eq.append(row)
    b_eq.append(0.0)

    A_ub, b_ub = [], []

    # Wuse_t <= pu_w[t]·P_w
    if pu_w is not None:
        pu_w = np.asarray(pu_w, dtype=float)
        for t in range(T):
            row = np.zeros(n)
            row[i_wu + t] = 1.0
            row[i_pw] = -pu_w[t]
            A_ub.append(row)
            b_ub.append(0.0)

    # Suse_t <= pu_s[t]·P_pv
    if pu_s is not None:
        pu_s = np.asarray(pu_s, dtype=float)
        for t in range(T):
            row = np.zeros(n)
            row[i_su + t] = 1.0
            row[i_ppv] = -pu_s[t]
            A_ub.append(row)
            b_ub.append(0.0)

    # ch_t <= P_ess, dis_t <= P_ess
    for t in range(T):
        row = np.zeros(n)
        row[i_ch + t] = 1.0
        row[i_pess] = -1.0
        A_ub.append(row)
        b_ub.append(0.0)
        row = np.zeros(n)
        row[i_dis + t] = 1.0
        row[i_pess] = -1.0
        A_ub.append(row)
        b_ub.append(0.0)

    # SOC 边界: E_t <= 0.9·E_ess, -E_t <= -0.1·E_ess
    for t in range(T + 1):
        row = np.zeros(n)
        row[i_e + t] = 1.0
        row[i_eess] = -SOC_HI
        A_ub.append(row)
        b_ub.append(0.0)
        row = np.zeros(n)
        row[i_e + t] = -1.0
        row[i_eess] = SOC_LO
        A_ub.append(row)
        b_ub.append(0.0)

    bounds = (
        [(0, None)] * T                              # buy
        + [(0, None)] * T                            # ch（上限经 A_ub 由 P_ess 约束）
        + [(0, None)] * T                            # dis
        + [(0, None) if pu_w is not None else (0, 0)] * T  # Wuse：无风电时必须为 0
        + [(0, None) if pu_s is not None else (0, 0)] * T  # Suse：无光伏时必须为 0
        + [(0, None)] * (T + 1)                      # E（上下限经 A_ub 由 E_ess 约束）
        + [(0, None) if pu_w is not None else (0, 0)]   # P_w
        + [(0, None) if pu_s is not None else (0, 0)]   # P_pv
        + [(0, None), (0, None)]                        # P_ess, E_ess
    )

    res = linprog(c, A_ub=np.array(A_ub), b_ub=np.array(b_ub),
                  A_eq=np.array(A_eq), b_eq=np.array(b_eq),
                  bounds=bounds, method="highs")
    if not res.success:
        raise RuntimeError(f"容量层 LP 求解失败: {res.message}")

    x = res.x
    return {
        "P_w": float(x[i_pw]),
        "P_pv": float(x[i_ppv]),
        "P_ess": float(x[i_pess]),
        "E_ess": float(x[i_eess]),
        "cost": float(res.fun),
    }


def solve_sizing_annual(L, pu_key_w, pu_key_s):
    """12 月耦合大 LP（Q3(2)）：12 场景共享容量变量，按月天数加权。

    参数
    ----
    L : (24,) 负荷（各月共用，波动特性不变）
    pu_key_w, pu_key_s : dict[int -> (24,)]，键 0~11 为月份，附件 3 数据；无该电源传 None

    返回
    ----
    dict: 容量 + 加权日总成本（年化/365）

    实现要点：12 场景 × 145 运行变量 + 4 共享容量变量 = 1744 个；
    目标按 DAYS_IN_MONTH 加权；分时电价 7:00-22:00 为 1 元、其余 0.4 元。
    """
    L = np.asarray(L, dtype=float)
    price = _price_vec(TOU_PRICE)
    M = 12
    per = 5 * T + (T + 1)  # 每场景运行变量数 145
    n = M * per + 4
    i_pw, i_ppv, i_pess, i_eess = n - 4, n - 3, n - 2, n - 1

    def idx(m, kind, t):
        base = m * per
        off = {0: 0, 1: T, 2: 2 * T, 3: 3 * T, 4: 4 * T, 5: 5 * T}[kind]
        return base + off + t

    c = np.zeros(n)
    c[i_pw] = WIND_COST / INV_PAYBACK
    c[i_ppv] = PV_COST / INV_PAYBACK
    c[i_pess] = ESS_P_COST / ESS_LIFE
    c[i_eess] = ESS_E_COST / ESS_LIFE

    A_eq, b_eq, A_ub, b_ub = [], [], [], []

    for m in range(M):
        days = DAYS_IN_MONTH[m]
        # 目标：运行成本按月天数加权
        for t in range(T):
            c[idx(m, 0, t)] = days * price[t]

        for t in range(T):
            # 功率平衡
            row = np.zeros(n)
            row[idx(m, 0, t)] = 1.0
            row[idx(m, 1, t)] = -1.0
            row[idx(m, 2, t)] = 1.0
            row[idx(m, 3, t)] = 1.0
            row[idx(m, 4, t)] = 1.0
            A_eq.append(row)
            b_eq.append(L[t])  # 负荷不加权，等式逐场景成立
            # SOC 递推
            row = np.zeros(n)
            row[idx(m, 5, t + 1)] = 1.0
            row[idx(m, 5, t)] = -1.0
            row[idx(m, 1, t)] = -ETA
            row[idx(m, 2, t)] = 1.0 / ETA
            A_eq.append(row)
            b_eq.append(0.0)

        # 循环约束
        row = np.zeros(n)
        row[idx(m, 5, T)] = 1.0
        row[idx(m, 5, 0)] = -1.0
        A_eq.append(row)
        b_eq.append(0.0)

        # Wuse / Suse 上限
        if pu_key_w is not None:
            pu = np.asarray(pu_key_w[m], dtype=float)
            for t in range(T):
                row = np.zeros(n)
                row[idx(m, 3, t)] = 1.0
                row[i_pw] = -pu[t]
                A_ub.append(row)
                b_ub.append(0.0)
        if pu_key_s is not None:
            pu = np.asarray(pu_key_s[m], dtype=float)
            for t in range(T):
                row = np.zeros(n)
                row[idx(m, 4, t)] = 1.0
                row[i_ppv] = -pu[t]
                A_ub.append(row)
                b_ub.append(0.0)

        # 充放电功率上限、SOC 边界（共享容量）
        for t in range(T):
            row = np.zeros(n)
            row[idx(m, 1, t)] = 1.0
            row[i_pess] = -1.0
            A_ub.append(row)
            b_ub.append(0.0)
            row = np.zeros(n)
            row[idx(m, 2, t)] = 1.0
            row[i_pess] = -1.0
            A_ub.append(row)
            b_ub.append(0.0)
        for t in range(T + 1):
            row = np.zeros(n)
            row[idx(m, 5, t)] = 1.0
            row[i_eess] = -SOC_HI
            A_ub.append(row)
            b_ub.append(0.0)
            row = np.zeros(n)
            row[idx(m, 5, t)] = -1.0
            row[i_eess] = SOC_LO
            A_ub.append(row)
            b_ub.append(0.0)

    bounds = []
    for m in range(M):
        bounds += (
            [(0, None)] * T                                    # buy
            + [(0, None)] * T                                  # ch
            + [(0, None)] * T                                  # dis
            + [(0, None) if pu_key_w is not None else (0, 0)] * T  # Wuse
            + [(0, None) if pu_key_s is not None else (0, 0)] * T  # Suse
            + [(0, None)] * (T + 1)                            # E
        )
    bounds += (
        [(0, None) if pu_key_w is not None else (0, 0)]
        + [(0, None) if pu_key_s is not None else (0, 0)]
        + [(0, None), (0, None)]
    )

    res = linprog(c, A_ub=np.array(A_ub), b_ub=np.array(b_ub),
                  A_eq=np.array(A_eq), b_eq=np.array(b_eq),
                  bounds=bounds, method="highs")
    if not res.success:
        raise RuntimeError(f"12 月耦合 LP 求解失败: {res.message}")

    x = res.x
    return {
        "P_w": float(x[i_pw]),
        "P_pv": float(x[i_ppv]),
        "P_ess": float(x[i_pess]),
        "E_ess": float(x[i_eess]),
        "cost": float(res.fun) / 365.0,  # 加权日总成本
    }
