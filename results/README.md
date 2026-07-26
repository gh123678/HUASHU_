# 结果输出目录

**本目录大部分文件被 .gitignore 忽略（*.csv），队友间通过以下方式同步：**

## 方式 1：自行生成（推荐）

```bash
pip install -r ../requirements.txt
cd ../src
python solve.py          # 复现 Q1–Q3 全部数值
python carbon.py         # 碳排放分析
python demand_response.py # 需求响应
python robust_opt.py     # 鲁棒优化
python battery_degradation.py # 电池衰减
python bonus.py          # DE 交叉验证 + 自由配置讨论 + 附录导出
```

所有脚本输出自动写入 `../results/`。

## 方式 2：网盘获取

建模手将 `results/` 打包上传至队内网盘，下载后解压到本目录即可。

---

## 文件清单（共 17 个 CSV）

### 主结果
| 文件 | 来源脚本 | 内容 |
|---|---|---|
| `附录_Q12_调度表_A.csv` | `bonus.py` | Q1(2) A 园区 24h 逐时段调度 |
| `附录_Q12_调度表_B.csv` | `bonus.py` | Q1(2) B 园区 24h 逐时段调度 |
| `附录_Q12_调度表_C.csv` | `bonus.py` | Q1(2) C 园区 24h 逐时段调度 |
| `附录_Q22_联合园区购电计划.csv` | `bonus.py` | Q2(2) 联合购电计划 |
| `附录_Q32_园区C_2月调度表.csv` | `bonus.py` | Q3(2) C 园区 2 月调度 |
| `附录_Q32_园区C_8月调度表.csv` | `bonus.py` | Q3(2) C 园区 8 月调度 |

### 加分项
| 文件 | 来源脚本 | 内容 |
|---|---|---|
| `碳排放分析汇总.csv` | `carbon.py` | 全场景碳排放对比 |
| `需求响应_多比例对比.csv` | `demand_response.py` | DR 0%–30% 多比例对比 |
| `需求响应_A园区_DR20pct_储能50-100.csv` | `demand_response.py` | A 园区 DR 20% 详细结果 |
| `鲁棒优化_不确定性扫描.csv` | `robust_opt.py` | 不确定度 0%–20% 扫描 |
| `鲁棒优化_储能对冲.csv` | `robust_opt.py` | 储能鲁棒对冲效应 |
| `电池衰减_配置对比.csv` | `battery_degradation.py` | 不同电池质量配置对比 |
| `电池衰减_循环寿命对比.csv` | `battery_degradation.py` | 6000 vs 10000 次循环 |
| `电池衰减_日历衰减曲线.csv` | `battery_degradation.py` | 10 年日历衰减曲线 |

### 交叉验证 & 讨论
| 文件 | 来源脚本 | 内容 |
|---|---|---|
| `交叉验证_Q31_DE_vs_LP.csv` | `bonus.py` | DE vs LP 对比（偏差 0.00%） |
| `模型讨论_A自由配置对比.csv` | `bonus.py` | A 可建风电 1584kW/3945 元 |
| `灵敏度4_负荷扰动_Q31.csv` | `bonus.py` | 负荷 40%–60% 对 Q3(1) 影响 |
