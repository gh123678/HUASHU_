# ============================================================================
# 注意：本脚本为队友初版实现（递进三层分析框架第二步），保留作为工作记录。
#
# 与统一 LP 方案（model.py + solve.py）的差异：
#   1. 调度算法：本脚本使用贪心规则（缺电则放、多电则充），非全局最优；
#      统一方案使用线性规划 solve_operation()，保证 24h 全局最优。
#   2. 成本计算：同 1.1，对全部风光发电量计费（含弃电）。
#   3. 论文中可作为"规则策略 vs 优化策略"的对比素材，
#      最终数值以 LP 结果为准。
# ============================================================================

import pandas as pd
import numpy as np

# 参数设置
STORAGE_POWER = 50  # 储能功率 (kW)
STORAGE_CAPACITY = 100  # 储能容量 (kWh)
SOC_MIN = 0.1  # SOC 最小值
SOC_MAX = 0.9  # SOC 最大值
CHARGE_EFFICIENCY = 0.95  # 充电效率
DISCHARGE_EFFICIENCY = 0.95  # 放电效率

GRID_COST = 1.0  # 主电网购电成本（元/kWh）
WIND_COST = 0.5  # 风电购电成本（元/kWh）
PV_COST = 0.4  # 光伏购电成本（元/kWh）

# 风光装机容量 (kW)
WIND_CAPACITY = {'园区A': 0, '园区B': 1000, '园区C': 500}
PV_CAPACITY = {'园区A': 750, '园区B': 0, '园区C': 600}


def optimize_storage(load_file, generation_file):
    # 1. 读取负荷数据与发电数据（跳过前3行表头说明，避免 KeyError）
    load_data = pd.read_csv(load_file)
    generation_data = pd.read_csv(generation_file, skiprows=3, header=None).iloc[:, :5]
    generation_data.columns = ['时间', '园区A光伏出力', '园区B风电出力', '园区C光伏出力', '园区C风电出力']

    for col in ['园区A光伏出力', '园区B风电出力', '园区C光伏出力', '园区C风电出力']:
        generation_data[col] = generation_data[col].astype(float)

    park_columns = ['园区A', '园区B', '园区C']
    results = {}

    for park in park_columns:
        load_demand = load_data[f'{park}负荷(kW)'].astype(float)

        # 确保发电数据为 Series 类型，即使装机容量为 0
        pv_power = generation_data[f'{park}光伏出力'] * PV_CAPACITY[park] if PV_CAPACITY[park] > 0 else pd.Series(0, index=load_demand.index)
        wind_power = generation_data[f'{park}风电出力'] * WIND_CAPACITY[park] if WIND_CAPACITY[park] > 0 else pd.Series(0, index=load_demand.index)
        total_power_generated = wind_power + pv_power

        # 确保负荷数据和发电数据长度一致
        T = min(len(load_demand), len(total_power_generated))
        load_demand = load_demand[:T]
        total_power_generated = total_power_generated[:T]

        soc = np.zeros(T)
        charge_power = np.zeros(T)
        discharge_power = np.zeros(T)
        purchase_power = np.zeros(T)

        current_soc = STORAGE_CAPACITY * SOC_MIN  # 初始SOC

        for t in range(T):
            net_load = load_demand.iloc[t] - total_power_generated.iloc[t]

            if net_load > 0:  # 供不应求，优先放电
                max_discharge = min(net_load, STORAGE_POWER,
                                    (current_soc - STORAGE_CAPACITY * SOC_MIN) * DISCHARGE_EFFICIENCY)
                discharge_power[t] = max_discharge
                current_soc -= discharge_power[t] / DISCHARGE_EFFICIENCY
                purchase_power[t] = net_load - discharge_power[t]
            else:  # 供大于求，优先充电
                max_charge = min(-net_load, STORAGE_POWER,
                                 (STORAGE_CAPACITY * SOC_MAX - current_soc) / CHARGE_EFFICIENCY)
                charge_power[t] = max_charge
                current_soc += charge_power[t] * CHARGE_EFFICIENCY
                purchase_power[t] = 0

            soc[t] = current_soc

        # 计算弃风弃光电量
        abandoned_power = (total_power_generated - load_demand - charge_power).clip(lower=0)

        wind_cost = (wind_power * WIND_COST).sum()
        pv_cost = (pv_power * PV_COST).sum()
        grid_cost = (purchase_power * GRID_COST).sum()

        total_cost = wind_cost + pv_cost + grid_cost
        average_cost = total_cost / load_demand.sum()

        results[park] = {
            '购电量 (kWh)': purchase_power.sum(),
            '弃风弃光电量 (kWh)': abandoned_power.sum(),
            '总供电成本 (元)': total_cost,
            '单位电量平均供电成本 (元/kWh)': average_cost
        }

    return results


if __name__ == "__main__":
    load_file = r"D:\桌面\A题：园区微电网风光储协调优化配置\csv_output\附件1：各园区典型日负荷数据_Sheet1.csv"
    generation_file = r"D:\桌面\A题：园区微电网风光储协调优化配置\csv_output\附件2：各园区典型日风光发电数据_Sheet1.csv"

    results = optimize_storage(load_file, generation_file)
    for park, park_results in results.items():
        print(f"园区: {park}")
        for key, value in park_results.items():
            print(f"  {key}: {value:.2f}")
