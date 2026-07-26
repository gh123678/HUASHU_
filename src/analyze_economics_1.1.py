import pandas as pd

# 参数设置
WIND_COST = 0.5  # 风电购电成本（元/kWh）
PV_COST = 0.4    # 光伏购电成本（元/kWh）
GRID_COST = 1.0  # 主电网购电成本（元/kWh）

# 更新风光装机容量参数
WIND_CAPACITY = {'园区A': 0, '园区B': 1000, '园区C': 500}  # 风电额定装机容量 (kW)
PV_CAPACITY = {'园区A': 750, '园区B': 0, '园区C': 600}     # 光伏额定装机容量 (kW)

def analyze_economics(load_file, generation_file):
    # 读取负荷数据和风光发电数据
    load_data = pd.read_csv(load_file)
    generation_data = pd.read_csv(generation_file, skiprows=1)  # 跳过说明行

    # 清理发电数据的列名
    generation_data.columns = generation_data.columns.str.strip()  # 去除列名中的空格
    generation_data = generation_data.rename(columns={
        '园区A光伏出力（p.u.）': '园区A光伏出力',
        '园区B风电出力（p.u.）': '园区B风电出力',
        '园区C光伏出力（p.u.）': '园区C光伏出力',
        '园区C风电出力（p.u.）': '园区C风电出力'
    })

    # 假设负荷数据列名为：时间（h）、园区A负荷(kW)、园区B负荷(kW)、园区C负荷(kW)
    park_columns = ['园区A', '园区B', '园区C']
    results = {}

    for park in park_columns:
        # 获取当前园区的负荷需求
        load_demand = load_data[f'{park}负荷(kW)']

        # 获取当前园区的风光发电量
        pv_power = generation_data[f'{park}光伏出力'] * PV_CAPACITY[park] if PV_CAPACITY[park] > 0 else 0
        wind_power = generation_data[f'{park}风电出力'] * WIND_CAPACITY[park] if WIND_CAPACITY[park] > 0 else 0

        # 计算购电量、弃风弃光电量
        total_power_generated = wind_power + pv_power
        purchase_power = (load_demand - total_power_generated).clip(lower=0)  # 购电量
        abandoned_power = (total_power_generated - load_demand).clip(lower=0)  # 弃风弃光电量

        # 计算总供电成本
        wind_cost = wind_power * WIND_COST
        pv_cost = pv_power * PV_COST
        grid_cost = purchase_power * GRID_COST
        total_cost = wind_cost + pv_cost + grid_cost

        # 计算单位电量平均供电成本
        average_cost = total_cost.sum() / load_demand.sum()

        # 保存当前园区的结果
        results[park] = {
            '购电量 (kWh)': purchase_power.sum(),
            '弃风弃光电量 (kWh)': abandoned_power.sum(),
            '总供电成本 (元)': total_cost.sum(),
            '单位电量平均供电成本 (元/kWh)': average_cost
        }

    return results

if __name__ == "__main__":
    # 替换为实际文件路径
    load_file = "/csv_output/附件1：各园区典型日负荷数据_Sheet1.csv"
    generation_file = "/csv_output/附件2：各园区典型日风光发电数据_Sheet1.csv"
    results = analyze_economics(load_file, generation_file)
    for park, park_results in results.items():
        print(f"园区: {park}")
        for key, value in park_results.items():
            print(f"  {key}: {value:.2f}")
