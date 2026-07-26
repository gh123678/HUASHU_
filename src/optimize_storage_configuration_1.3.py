import os
import numpy as np
import pandas as pd
from scipy.optimize import Bounds, LinearConstraint, milp

# ==================== 参数设置 ====================
SOC_MIN = 0.1  # SOC 最小值
SOC_MAX = 0.9  # SOC 最大值
CHARGE_EFFICIENCY = 0.95  # 充电效率
DISCHARGE_EFFICIENCY = 0.95  # 放电效率

GRID_COST = 1.0  # 主电网购电成本（元/kWh）
WIND_COST = 0.5  # 风电购电成本（元/kWh）
PV_COST = 0.4  # 光伏购电成本（元/kWh）

# 储能设备投资成本参数 (全生命周期 10 年)
POWER_UNIT_COST = 800  # 元/kW
ENERGY_UNIT_COST = 1800  # 元/kWh
LIFETIME_DAYS = 10 * 365  # 3650天

# 风光装机容量 (kW)
WIND_CAPACITY = {"园区A": 0, "园区B": 1000, "园区C": 500}
PV_CAPACITY = {"园区A": 750, "园区B": 0, "园区C": 600}


def _to_finite_series(series, name):
    """将输入转换为有限数值序列；若存在缺失/非法值则报错。"""
    cleaned = (
        pd.to_numeric(series, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .reset_index(drop=True)
    )
    if cleaned.isna().any():
        invalid_idx = cleaned[cleaned.isna()].index.tolist()
        raise ValueError(
            f"{name} 包含缺失或非数值数据，无法进行优化；问题行索引: {invalid_idx[:10]}"
        )
    return cleaned.to_numpy(dtype=float)


def optimize_storage_linear(
    load_demand, pv_power, wind_power, storage_power, storage_capacity
):
    """使用线性规划优化给定储能配置下的日运行策略"""
    load_demand = np.asarray(load_demand, dtype=float)
    pv_power = np.asarray(pv_power, dtype=float)
    wind_power = np.asarray(wind_power, dtype=float)
    total_gen = pv_power + wind_power

    T = len(load_demand)

    # 若未配置储能 (0 kW / 0 kWh)
    if storage_power == 0 or storage_capacity == 0:
        initial_soc = 0.0
    else:
        initial_soc = storage_capacity * SOC_MIN

    n_vars = 5 * T

    grid_offset = 0
    charge_offset = T
    discharge_offset = 2 * T
    soc_offset = 3 * T
    curtail_offset = 4 * T

    # 1. 目标函数系数 (微弱惩罚充放电以防无意义充放)
    c = np.zeros(n_vars)
    c[grid_offset:charge_offset] = GRID_COST
    c[charge_offset:discharge_offset] = 1e-5
    c[discharge_offset:soc_offset] = 1e-5

    # 2. 变量上下界
    lb = np.zeros(n_vars)
    ub = np.zeros(n_vars)

    ub[grid_offset:charge_offset] = np.inf
    ub[charge_offset:discharge_offset] = storage_power
    ub[discharge_offset:soc_offset] = storage_power

    if storage_capacity > 0:
        lb[soc_offset:curtail_offset] = storage_capacity * SOC_MIN
        ub[soc_offset:curtail_offset] = storage_capacity * SOC_MAX
    else:
        lb[soc_offset:curtail_offset] = 0.0
        ub[soc_offset:curtail_offset] = 0.0

    ub[curtail_offset:] = np.inf

    # 3. 等式约束
    A_eq = []
    b_eq = []

    # 约束 A: 功率平衡
    for t in range(T):
        row = np.zeros(n_vars)
        row[grid_offset + t] = 1.0
        row[charge_offset + t] = -1.0
        row[discharge_offset + t] = 1.0
        row[curtail_offset + t] = -1.0
        A_eq.append(row)
        b_eq.append(load_demand[t] - total_gen[t])

    # 约束 B: SOC 连续性
    for t in range(T):
        row = np.zeros(n_vars)
        row[soc_offset + t] = 1.0
        row[charge_offset + t] = -CHARGE_EFFICIENCY
        row[discharge_offset + t] = 1.0 / DISCHARGE_EFFICIENCY
        if t == 0:
            b_eq.append(initial_soc)
        else:
            row[soc_offset + t - 1] = -1.0
            b_eq.append(0.0)
        A_eq.append(row)

    # 约束 C: 日终 SOC 恢复
    row_end = np.zeros(n_vars)
    row_end[soc_offset + T - 1] = 1.0
    A_eq.append(row_end)
    b_eq.append(initial_soc)

    # 4. 求解 MILP / LP
    result = milp(
        c=c,
        integrality=np.zeros(n_vars, dtype=int),
        bounds=Bounds(lb, ub),
        constraints=LinearConstraint(
            np.array(A_eq), np.array(b_eq), np.array(b_eq)
        ),
    )

    if result.success:
        x = result.x
        purchase_power = x[grid_offset:charge_offset]
        curtail_power = x[curtail_offset:]

        total_curtail_kWh = np.sum(curtail_power)
        total_gen_kWh = np.sum(total_gen)

        if total_gen_kWh > 0:
            pv_used_kWh = np.sum(pv_power) * (
                1 - total_curtail_kWh / max(total_gen_kWh, 1e-6)
            )
            wind_used_kWh = np.sum(wind_power) * (
                1 - total_curtail_kWh / max(total_gen_kWh, 1e-6)
            )
        else:
            pv_used_kWh = 0.0
            wind_used_kWh = 0.0

        grid_purchase_kWh = np.sum(purchase_power)
        daily_op_cost = (
            grid_purchase_kWh * GRID_COST
            + pv_used_kWh * PV_COST
            + wind_used_kWh * WIND_COST
        )

        return grid_purchase_kWh, total_curtail_kWh, daily_op_cost
    else:
        raise ValueError(f"求解失败，状态码: {result.status}")


def optimize_storage(load_file, generation_file):
    # 读取负荷与发电数据
    load_data = pd.read_csv(load_file)
    generation_data = pd.read_csv(
        generation_file, skiprows=1, header=0
    ).iloc[:, :5]
    generation_data.columns = [
        "时间",
        "园区A光伏出力",
        "园区B风电出力",
        "园区C光伏出力",
        "园区C风电出力",
    ]

    for col in [
        "园区A光伏出力",
        "园区B风电出力",
        "园区C光伏出力",
        "园区C风电出力",
    ]:
        generation_data[col] = pd.to_numeric(
            generation_data[col], errors="coerce"
        )

    park_columns = ["园区A", "园区B", "园区C"]
    results = {}

    for park in park_columns:
        load_demand = _to_finite_series(
            load_data[f"{park}负荷(kW)"], f"{park}负荷(kW)"
        )

        if PV_CAPACITY[park] > 0:
            pv_power = (
                _to_finite_series(
                    generation_data[f"{park}光伏出力"], f"{park}光伏出力"
                )
                * PV_CAPACITY[park]
            )
        else:
            pv_power = np.zeros(len(load_demand), dtype=float)

        if WIND_CAPACITY[park] > 0:
            wind_power = (
                _to_finite_series(
                    generation_data[f"{park}风电出力"], f"{park}风电出力"
                )
                * WIND_CAPACITY[park]
            )
        else:
            wind_power = np.zeros(len(load_demand), dtype=float)

        common_len = min(len(load_demand), len(pv_power), len(wind_power))
        load_demand = load_demand[:common_len]
        pv_power = pv_power[:common_len]
        wind_power = wind_power[:common_len]

        best_config = None
        best_total_cost = float("inf")

        # 网格搜索功率与容量配置 (含 0/0 基线方案)
        # 功率范围: 0 ~ 200 kW (步长 10kW)
        # 容量范围: 0 ~ 400 kWh (步长 10kWh)
        for storage_power in range(0, 201, 10):
            for storage_capacity in range(0, 401, 10):
                # 排除异常状态：功率与容量必须同为0或同大于0
                if (storage_power == 0 and storage_capacity > 0) or (
                    storage_power > 0 and storage_capacity == 0
                ):
                    continue

                # 1. 每日运行成本 (购电费)
                purchase_power, abandoned_power, daily_op_cost = (
                    optimize_storage_linear(
                        load_demand,
                        pv_power,
                        wind_power,
                        storage_power,
                        storage_capacity,
                    )
                )

                # 2. 每日设备折旧成本 (CAPEX)
                daily_depreciation = (
                    storage_power * POWER_UNIT_COST
                    + storage_capacity * ENERGY_UNIT_COST
                ) / LIFETIME_DAYS

                # 3. 真实每日总成本
                real_total_cost = daily_op_cost + daily_depreciation

                if real_total_cost < best_total_cost:
                    best_total_cost = real_total_cost
                    best_config = {
                        "最佳储能功率 (kW)": storage_power,
                        "最佳储能容量 (kWh)": storage_capacity,
                        "网购电量 (kWh)": round(purchase_power, 2),
                        "弃风弃光电量 (kWh)": round(abandoned_power, 2),
                        "运行购电成本 (元)": round(daily_op_cost, 2),
                        "每日设备折旧 (元)": round(daily_depreciation, 2),
                        "真实每日总成本 (元)": round(real_total_cost, 2),
                    }

        results[park] = best_config

    return results


if __name__ == "__main__":
    # 自动定位项目中的 csv_output 目录，从脚本目录回退至项目根目录
    script_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.abspath(os.path.join(script_dir, ".."))
    csv_dir = os.path.join(project_root, "csv_output")

    load_file = os.path.join(csv_dir, "附件1：各园区典型日负荷数据_Sheet1.csv")
    generation_file = os.path.join(
        csv_dir, "附件2：各园区典型日风光发电数据_Sheet1.csv"
    )

    if not os.path.exists(load_file) or not os.path.exists(generation_file):
        raise FileNotFoundError(
            f"找不到输入文件，请确认 {load_file} 和 {generation_file} 存在"
        )

    results = optimize_storage(load_file, generation_file)
    for park, park_results in results.items():
        print(f"\n======== {park} 全局最优配置结果 ========")
        for key, value in park_results.items():
            print(f"  {key}: {value}")
