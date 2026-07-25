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

from model import solve_operation, solve_sizing, solve_sizing_annual
from utils import load_load, load_typical_day, load_monthly, check_power_balance


def sweep_storage(L, W, S, Prange, Erange, **lp_kwargs):
    """Q1(3)/Q2(2) 储能配置二维网格扫描（方案 6.1 模块 3）。

    每个 (P_ess, E_ess) 解一次 solve_operation，日总成本 = 运行成本 + 储能投资日分摊，
    取最小。粗扫 10kW/20kWh 步长 + 最优点附近加密 5kW/10kWh。

    为何不用一步 LP：扫描产出"容量—日总成本"等值线图（论文图证），
    并揭示边际收益递减规律；一步 LP 只给一个点。

    返回
    ----
    dict: P_opt, E_opt, cost_opt, grid(扫描结果矩阵, 供绘等值线图)
    """
    raise NotImplementedError


def q1():
    """问题1：独立园区基线 / 50kW-100kWh 评估 / 最优储能扫描。

    复现基准：方案 4.1 / 4.2 / 4.3 节表格。
    解析基线注意：C 园区先消纳光伏(0.4元)再消纳风电(0.5元)，弃电优先弃风电。
    """
    raise NotImplementedError


def q2():
    """问题2：三园区功率逐时叠加后联合运营，对比独立合计。

    复现基准：方案 4.4 节表格（联合后最优储能为 0 是核心结论）。
    """
    raise NotImplementedError


def q3():
    """问题3：负荷×1.5 的风光储协调配置。

    3(1) 固定电价单 LP（复现 4.5）；3(2) 12 月耦合 + 分时电价（复现 4.6）。
    注意：Q3 风光为自建资产，solve_operation/solve_sizing 中电量费传 0。
    """
    raise NotImplementedError


def sensitivity():
    """灵敏度分析三组实验（方案 6.3，加分项）：
    1. 储能能量单价 1800 -> 1440/900 元/kWh，重跑 Q1(3)，找 A 园区临界点单价；
    2. 网购电价 ±20% 对 Q1(3)/Q2(2) 最优容量的影响；
    3. 投资回报期 5 年 -> 8 年对 Q3 装机的影响。
    """
    raise NotImplementedError


if __name__ == "__main__":
    # TODO: 依次运行 q1() -> q3()，打印结果表格并与方案第 4 节对比，
    # 最后跑 check_power_balance 等自洽性检查，全过才算完成。
    pass
