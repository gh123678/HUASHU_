# 华数杯数模竞赛 · A题：园区微电网风光储协调优化配置

> 三人小组协作仓库：建模手 / 代码手 / 论文手
> 核心方法：全题共用一个**线性规划（LP）核心模型**，三问只是边界条件和决策变量层级不同。
> 求解工具：`scipy.optimize.linprog`（HiGHS 求解器），**全程不需要智能算法**。

---

## 一、题目速览

园区微电网（A 纯光伏 / B 纯风电 / C 风光兼有）+ 磷酸铁锂储能，三问层层递进：

| 问题 | 内容 | 方法 |
|---|---|---|
| Q1 | 独立园区经济性分析 + 储能配置寻优 | 解析 + 单 LP + 二维网格扫描 |
| Q2 | 三园区联合运营对比 | 功率叠加后同 Q1 |
| Q3 | 负荷×1.5 下风光储协调配置（自建资产） | 容量直接进 LP；3(2) 为 12 月耦合大 LP |

**总体建模方案（全队必读，口径以此为准）**：[`docs/总体建模方案.md`](docs/总体建模方案.md)

已定关键约定（改动前必须全队讨论）：
1. Q3 风光视为自建资产，**投资分摊、不计 0.5/0.4 元电量费**；
2. Q3 各园区**保持原有电源类型**；
3. 弃电时**优先弃贵的风电**（先消纳光伏 0.4 元，再风电 0.5 元）。

---

## 二、仓库结构

```
HUASHU_/
├── data/                  # 原始数据（已加 .gitignore，不上传！太大放网盘）
│   └── README.md          #   说明数据从哪下载、放哪
├── src/                   # 代码（代码手主写）
│   ├── model.py           #   核心 LP 模型：运行调度 + 容量配置
│   ├── solve.py           #   求解脚本：复现各问结果、扫描、出表
│   └── utils.py           #   工具函数：数据读取、绘图、校验
├── docs/                  # 论文相关（论文手主写）
│   ├── 总体建模方案.md     #   建模手定稿的全队方案（勿擅改）
│   ├── paper.md           #   论文草稿（Markdown，最后转 Word）
│   └── figures/           #   生成的图（150dpi 以上、中文标注）
├── results/               # 输出结果（已加 .gitignore，不上传）
├── README.md              # 本文件：分工、进度、运行说明
└── requirements.txt       # Python 依赖
```

## 三、三人分工

| 角色 | 主要负责 | 避免冲突技巧 |
|---|---|---|
| 代码手 | `src/` 目录 | 每人改不同 `.py` 文件，别同时改同一个 |
| 论文手 | `docs/` 目录 | 论文用 Markdown 写，最后转 Word |
| 建模手 | `data/`、README、方案文档 | 数据放网盘链接；README 更新前先发群里 |

**核心原则**
- 不要两个人同时改同一个文件；
- 每天开工前 `git pull`，收工前 `git push`；
- 大文件（数据、图片）别传 GitHub，放网盘 / Release。

## 四、每日协作流程

### 1. 开工前：拉最新代码

```bash
git pull origin main
```

### 2. 干活时：各自建分支（防冲突）

```bash
# 代码手
git checkout -b feature-model-q2

# 论文手
git checkout -b docs-paper-section3

# 建模手
git checkout -b data-preprocessing
```

分支命名规则：`类型-内容`，如 `fix-bug`、`feature-sweep`、`docs-abstract`。

### 3. 改完推上去

```bash
git add .
git commit -m "Q2模型完成，加入扫描法"
git push origin feature-model-q2
```

### 4. 合并到主分支

- 推荐：GitHub 网页点 **Compare & pull request** → 队友看一眼 → Merge；
- 时间紧时直接：

```bash
git checkout main
git merge feature-model-q2
git push origin main
```

## 五、冲突了怎么办（merge conflict）

```bash
git pull origin main          # 拉下来，会显示冲突
# 打开冲突文件，找到 <<<<<<< HEAD 标记
# 手动保留想要的内容，删掉标记
git add .
git commit -m "解决冲突"
git push origin main
```

## 六、数模专用注意事项

| ⚠️ 坑 | 解决方案 |
|---|---|
| 有人忘 pull 直接 push | 先 `git pull`，有冲突解决完再 push |
| 数据文件 push 上去仓库爆炸 | `data/`、`results/` 已写进 `.gitignore` |
| 代码跑不通就 push | push 前本地跑一遍 `python src/solve.py` |
| 论文手不会 Git | 论文用 Markdown 写，代码手帮忙合并；或写本地定时传网盘 |
| 最后一天乱合并搞崩 | **比赛结束前 2 小时冻结 main 分支，只修 bug** |

## 七、运行说明（代码手补全后更新）

```bash
# 安装依赖
pip install -r requirements.txt

# 复现全部数值结果（验收基准：与 docs/总体建模方案.md 第 4 节逐位对上，±0.5%）
python src/solve.py
```

**代码验收两项自洽性检查**：
1. 储能容量趋零时 LP 结果退化为解析基线；
2. 最优解逐时段功率平衡残差 < 1e-6，SOC 轨迹在 [10%, 90%] 内。

## 八、进度看板

| 事项 | 状态 | 负责人 |
|---|---|---|
| 核心 LP 模型与全部数值结果 | ✅ 已验证 | 建模手 |
| 代码模块化重构 + 全部图表 | 🔲 待做 | 代码手 |
| 论文初稿（按方案 6.2 节结构） | 🔲 待做 | 论文手 |
| 灵敏度分析三组实验 | 🔲 待做 | 代码手跑数 + 论文手成文 |
| 逐时段调度表（附录） | 🔲 待出 | 代码手 |
| 交叉校验：论文数字 vs 代码输出 | 🔲 提交前必做 | 全员 |

## 九、每日 checklist

```
□ git pull origin main
□ git checkout -b 你的分支
□ 干活
□ 本地测试能跑通
□ git add . → git commit -m "清晰描述"
□ git push origin 你的分支
□ GitHub 上发 Pull Request / 合并
□ 群里喊一声"我合了 main，你们 pull 一下"
```
