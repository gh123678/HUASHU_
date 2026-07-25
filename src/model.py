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
    raise NotImplementedError("代码手按 docs/总体建模方案.md 6.1 模块 2 实现")


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
    """
    raise NotImplementedError("代码手按方案 6.1 模块 4 实现")


def solve_sizing_annual(L, pu_key_w, pu_key_s):
    """12 月耦合大 LP（Q3(2)）：12 场景共享容量变量，按月天数加权。

    参数
    ----
    L : (24,) 负荷（各月共用，波动特性不变）
    pu_key_w, pu_key_s : dict[int -> (24,)]，键 0~11 为月份，附件 3 数据

    返回
    ----
    dict: 容量 + 加权日总成本

    实现要点：约 1744 个变量；容量变量 12 场景共享；
    目标按 DAYS_IN_MONTH 加权；分时电价 7:00-22:00 为 1 元、其余 0.4 元。
    """
    raise NotImplementedError("代码手按方案 6.1 模块 4 实现")
