# -*- coding: utf-8 -*-
"""
utils.py — 工具函数：数据读取 / 绘图 / 校验（代码手主写）

数据文件放 data/ 目录（不上传 GitHub，见 data/README.md）。
时间粒度 1h，Δt=1h，故功率(kW)数值上等于该时段电量(kWh)，绘图时注意单位表述。
"""

import os

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# 中文标注（论文图全部要求中文）
# 字体降级链：SimHei → Microsoft YaHei → WenQuanYi → Noto Sans CJK → sans-serif
plt.rcParams["font.sans-serif"] = ["SimHei", "Microsoft YaHei", "WenQuanYi Micro Hei", "Noto Sans CJK SC", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
ATTACH_DIR = os.path.join(DATA_DIR, "A题：园区微电网风光储协调优化配置")

# 各园区装机容量（题目图1给定，kW）。注意：C 光伏是 600（联合 1350=750+600 佐证），
# docs/总体建模方案.md §1.1 表格误写为 500，以题目为准
PV_CAP = {"A": 750.0, "B": 0.0, "C": 600.0}
WIND_CAP = {"A": 0.0, "B": 1000.0, "C": 500.0}

FIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "figures")
os.makedirs(FIG_DIR, exist_ok=True)


def _attach_path(name):
    return os.path.join(ATTACH_DIR, name)


def load_load(path=None):
    """附件1：三园区 24h 负荷（kW）。

    注意表头偏移：第 2 行起为数据，列：时间/A/B/C。
    返回 dict: {"A": (24,), "B": (24,), "C": (24,)}
    """
    if path is None:
        path = _attach_path("附件1：各园区典型日负荷数据.xlsx")
    df = pd.read_excel(path, header=0)
    return {
        "A": df.iloc[:24, 1].to_numpy(dtype=float),
        "B": df.iloc[:24, 2].to_numpy(dtype=float),
        "C": df.iloc[:24, 3].to_numpy(dtype=float),
    }


def load_typical_day(path=None):
    """附件2：典型日风光出力标幺值（Q1/Q2 用）。

    注意表头偏移：第 4 行起为数据，列：时间/A光伏/B风电/C光伏/C风电。
    实际功率 = 标幺值 × 装机容量（A:750kW 光伏, B:1000kW 风电, C:600光伏+500风电）。
    返回 dict: {"A_pv": (24,), "B_w": (24,), "C_pv": (24,), "C_w": (24,)}（标幺值）
    """
    if path is None:
        path = _attach_path("附件2：各园区典型日风光发电数据.xlsx")
    df = pd.read_excel(path, header=None, skiprows=3)
    data = df.iloc[:24, 1:5].to_numpy(dtype=float)
    return {
        "A_pv": data[:, 0],
        "B_w": data[:, 1],
        "C_pv": data[:, 2],
        "C_w": data[:, 3],
    }


def load_monthly(path=None):
    """附件3：12 个月典型日标幺值（Q3(2) 用）。

    注意表头偏移：第 5 行起为数据，每月 4 列（A光伏/B风电/C风电/C光伏），共 48 列。
    已验证事实：附件3 的 2 月光伏与附件2 完全一致，但附件2 风电≠附件3 任何一个月
    ——两者用途不同，互不冲突，不要混用。
    返回 dict[int -> dict[str, (24,)]]，键 0~11 为月份，值含 A_pv/B_w/C_pv/C_w。
    """
    if path is None:
        path = _attach_path("附件3：12个月各园区典型日风光发电数据.xlsx")
    df = pd.read_excel(path, header=None, skiprows=4)
    out = {}
    for m in range(12):
        block = df.iloc[:24, 1 + 4 * m: 5 + 4 * m].to_numpy(dtype=float)
        out[m] = {
            "A_pv": block[:, 0],
            "B_w": block[:, 1],
            "C_w": block[:, 2],
            "C_pv": block[:, 3],
        }
    return out


def typical_day_power():
    """Q1/Q2 用：各园区实际负荷与风光功率（kW）。

    返回 dict: 每园区 {"L": (24,), "W": (24,), "S": (24,)}
    """
    load = load_load()
    pu = load_typical_day()
    parks = {}
    for p in ("A", "B", "C"):
        parks[p] = {
            "L": load[p],
            "W": pu.get(f"{p}_w", np.zeros(24)) * WIND_CAP[p],
            "S": pu.get(f"{p}_pv", np.zeros(24)) * PV_CAP[p],
        }
    return parks


def check_power_balance(res, L, P_ess, E_ess, tol=1e-6):
    """自洽性检查：最优解逐时段功率平衡残差 < tol，SOC 轨迹在 [10%, 90%] 内。

    功率平衡：Wuse + Suse + dis + buy = L + ch（弃电为 W-Wuse、S-Suse）
    """
    lhs = res["Wu"] + res["Su"] + res["dis"] + res["buy_t"]
    rhs = L + res["ch"]
    residual = np.max(np.abs(lhs - rhs))
    assert residual < tol, f"功率平衡残差 {residual:.2e} 超过 {tol}"
    E = np.asarray(res["E"])
    lo, hi = 0.1 * E_ess, 0.9 * E_ess
    assert E.min() >= lo - 1e-6, f"SOC 低于下限: {E.min():.3f} < {lo:.3f}"
    assert E.max() <= hi + 1e-6, f"SOC 高于上限: {E.max():.3f} > {hi:.3f}"
    assert np.all(np.asarray(res["ch"]) <= P_ess + 1e-6), "充电功率越限"
    assert np.all(np.asarray(res["dis"]) <= P_ess + 1e-6), "放电功率越限"
    assert abs(E[-1] - E[0]) < tol, "SOC 循环约束不满足"
    return True
