# -*- coding: utf-8 -*-
"""
utils.py — 工具函数：数据读取 / 绘图 / 校验（代码手主写）

数据文件放 data/ 目录（不上传 GitHub，见 data/README.md）。
时间粒度 1h，Δt=1h，故功率(kW)数值上等于该时段电量(kWh)，绘图时注意单位表述。
"""

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# 中文标注（论文图全部要求中文）
plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False

DATA_DIR = "../data"   # 相对 src/ 运行时的数据目录


def load_load(path):
    """附件1：三园区 24h 负荷（kW）。

    注意表头偏移：第 2 行起为数据，列：时间/A/B/C。
    返回 dict: {"A": (24,), "B": (24,), "C": (24,)}
    """
    raise NotImplementedError


def load_typical_day(path):
    """附件2：典型日风光出力标幺值（Q1/Q2 用）。

    注意表头偏移：第 4 行起为数据，列：时间/A光伏/B风电/C光伏/C风电。
    实际功率 = 标幺值 × 装机容量（A:750kW 光伏, B:1000kW 风电, C:500+500）。
    返回 dict: {"A_pv": (24,), "B_w": (24,), "C_pv": (24,), "C_w": (24,)}
    """
    raise NotImplementedError


def load_monthly(path):
    """附件3：12 个月典型日标幺值（Q3(2) 用）。

    注意表头偏移：第 5 行起为数据，每月 4 列（A光伏/B风电/C风电/C光伏），共 48 列。
    已验证事实：附件3 的 2 月光伏与附件2 完全一致，但附件2 风电≠附件3 任何一个月
    ——两者用途不同，互不冲突，不要混用。
    返回 dict[int -> dict[str, (24,)]]，键 0~11 为月份。
    """
    raise NotImplementedError


def check_power_balance(res, L, tol=1e-6):
    """自洽性检查：最优解逐时段功率平衡残差 < tol，SOC 轨迹在 [10%, 90%] 内。

    另需检查：储能容量趋零时 LP 结果退化为解析基线（在 solve.py 主流程调用）。
    """
    raise NotImplementedError


# ---- 绘图清单（论文用，全部中文标注、150dpi 以上，存 docs/figures/） ----
# 1. 三园区负荷曲线图（图2复现）
# 2. Q1(2) 各园区逐时功率堆叠图 + SOC 轨迹（3 张子图）
# 3. Q1(3) 储能容量—日总成本等值线图（每园区 1 张，标注 50/100 点与最优点）
# 4. Q2 独立 vs 联合逐时净负荷对比图、购电/弃电/成本对比柱状图
# 5. Q3(2) 典型月（2 月与 8 月）逐时调度堆叠图 + SOC 轨迹
# 6. 灵敏度分析图
def plot_example():
    raise NotImplementedError("按上方清单逐个实现绘图函数")
