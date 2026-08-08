---
name: 3coding-visual
description: "数学建模编程实现与数据图表生成阶段。根据 ANALYSIS_MODELING_REPORT.md 编写可复现代码、运行求解、验证约束、输出 RESULTS_REPORT.md 并生成论文可用的数据驱动图表 PDF。"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch
---

# 编程实现与数据图表生成

本 skill 承接 `2analysis-modeling`。目标是把 `reports/ANALYSIS_MODELING_REPORT.md` 里的模型和算法落实为可复现程序，跑出可信结果，并生成论文中需要的数据型图表。

## 数学建模规范参考

如需领域判断，读取 `../_references/math_modeling_norms.md` 中的“题型防错速查”“代码实现与结果”“编码阶段常见错误”和“图表与可视化”小节。该文件只作为规范知识库，不新增本阶段的固定产物。

## 阶段边界

- 本阶段负责：代码、实验运行、结果、结果表、数据驱动图表。
- 本阶段不负责：技术路线图、算法流程图、系统架构图、概念示意图。这些交给 `4drawio`。
- 本阶段不写论文正文，只为 `5writing` 提供可信数值和图表资产。


### Step 1: 代码结构

按 `plan.md` 中"项目目录结构"创建 `code/` 和 `figures/` 骨架，再开始写代码。子问题数不一定是 3，按赛题实际数量调整。


### Step 2: 逐子问题实现

按子问题顺序实现，不要一次性写完不跑。

每个子问题必须完成：

1. 读取所需数据。
2. 实现模型或算法。
3. 验证约束。
4. 输出核心结果。
5. 绘制丰富的图表。
6. 在 `reports/RESULTS_REPORT.md` 中写清楚方法、关键数值和校验结果。

优化类问题必须先保证可行解，再优化目标值。预测类问题必须做训练/验证划分或合理误差评估。评价类问题必须说明指标方向、归一化方法和权重来源。

### Step 3: 结果文件格式


AI 在实现、求解和作图过程中，必须把关键中间过程保存成数据并做好记录，例如清洗后的数据摘要、模型参数、迭代历史、约束检查、灵敏度分析过程、图表所用数据和运行日志。中间数据优先保存到 `figures/` 或 `code/outputs/`，并在 `reports/RESULTS_REPORT.md` 中说明文件用途。

`reports/RESULTS_REPORT.md` 推荐结构：

```markdown
# 计算结果

## 运行环境
## 数据读取与预处理
## 问题一结果
## 问题二结果
## 问题三结果
## 灵敏度分析
## 约束与一致性校验
## 与建模报告的一致性说明
## 可复现运行方式
```

所有数据和图表结果都必须出现在 `reports/RESULTS_REPORT.md` 中引用

### Step 3.1：结构化结果契约（必须）

每个子问题必须额外写出 `results/<子问题>.json`，禁止只把数字打印在日志或写进论文。文件至少包含：

```json
{
  "schema_version": "1.0",
  "status": "success",
  "task": "ques1",
  "data_hashes": ["sha256:..."],
  "sample": {"n_total": 0, "n_train": 0, "n_validation": 0},
  "metrics": {"mae": 0.0, "rmse": 0.0},
  "parameters": {},
  "artifacts": ["figures/ques1.png"],
  "validation": {
    "time_split": "train<=...; validation=...",
    "independent_recompute": true,
    "constraints_passed": true
  },
  "limitations": [],
  "error": null
}
```

`status=success` 的前提是代码至少成功执行一次、结果 JSON 可解析、声明的产物存在、约束检查通过，并完成一次独立重算或等价的结果复核。失败时使用 `status=failed` 并填写 `error`；失败结果不得交给 `5writing`。

### Step 3.2：数据和时间序列闸门

运行前生成 `data/data_manifest.json`，记录来源、接收时间、SHA-256、字段单位、行列数和缺失率。训练/验证/回放按时间先后切分，禁止随机打乱时序样本。标准化、缺失填补和目标编码只能在训练集拟合，再应用于验证集；代码必须打印实际切分边界和有效样本量。样本少于参数量的模型不得作为主模型，除非报告明确降级并解释原因。

### Step 3.3：独立复核

代码手完成主计算后，必须用独立函数、独立参数重建或保存的中间表重新计算至少一个核心指标和一个关键结论。两次结果的绝对差必须写入 JSON；超过 `1e-6`（或报告中声明的数值容差）则标记 `verification_failed`。

### Step 4: 生成数据驱动图表

根据 `reports/ANALYSIS_MODELING_REPORT.md` 和 `reports/RESULTS_REPORT.md` 规划图表，生成 PDF 到 `figures/`。

典型图表：

- 预测类：真实值-预测值对比、误差分布、指标对比。
- 优化类：收敛曲线、成本对比、资源利用率、方案前后对比。
- 评价类：综合得分排序、雷达图、热力图、敏感性曲线。
- 数据理解：分布图、趋势图、相关性图、箱线图。

图表要求：

- PDF 矢量输出，适合论文。
- 不在图内写大标题，标题交给论文 caption（Typst 的 `caption:` 或 LaTeX 的 `\caption{}`）。
- 中文论文图表使用中文坐标轴和图例；英文论文使用英文。
- 不生成流程图/架构图/路线图。

图表可以由主程序或独立脚本生成，不强制固定脚本名。无论采用哪种方式，都必须保存图表对应的数据来源和生成记录。

### Step 5：交接阻断

代码阶段结束前，逐个检查 `results/*.json`。任何子问题缺少结果文件、数据哈希、样本量、验证记录或图表路径时，必须阻断写作阶段，并在 `reports/RESULTS_REPORT.md` 中给出可操作的修复项。写作手只能读取通过闸门的结构化结果，不能从自然语言错误日志猜测数值。
