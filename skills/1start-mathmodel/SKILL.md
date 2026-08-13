---
name: 1start-mathmodel
description: "数学建模竞赛工作流入口。用于启动完整建模流程：询问用户偏好，生成 plan.md 和 todo.md，并按阶段调用赛题分析、建模、代码与图表、流程图、论文撰写、验证验收等 skills；对题面含计算、存储、时间、成本或资源优化目标的任务，强制建立可复算资源基线和帕累托验收。"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch
---

# 数学建模工作流

本 skill 是数学建模竞赛项目的总控入口。它不替代后续阶段 skill，而是负责启动流程、询问偏好、记录决策、生成计划，并按顺序调用各阶段 skill。

## 研究证据与题目契约

启动时先锁定真实题面和对标证据，再让下游阶段建模。用户要求学习竞赛资料时，建立 `reports/SOURCE_MANIFEST.md`，至少记录题面来源、附件来源、抓取时间、SHA-256、相关论文目录和选定代表性优秀论文（年份、题号、队伍/论文编号、页数、选择理由）。如果用户要求“全部查看”，必须按目录逐项记录处理状态；不能只看一篇论文后声称已完成全部资料学习。

同时建立 `reports/QUESTION_COVERAGE.md`，逐个顶层问题登记：题面原文位置、输出对象、参数边界、场景组合、理论模型、仿真实验、图表、结论和验证状态。任何题面条件未覆盖，都要标为 `gap`，不得在摘要中写成已完成。

最终输出目录必须以实际探测到的工作根目录为准，并写入 `plan.md`。禁止把示例路径、容器路径或不存在的目录写进验收结论。

## 数学建模规范参考

如需领域判断，读取 `../_references/math_modeling_norms.md`。该文件只提供数学建模基本规范和防错知识，不改变本 skill 的阶段顺序和产出约定。

## 必须产出

在当前工作目录中创建或更新以下文件：

- `plan.md`：整体流程方案、建模方向、阶段顺序、预期产物和风险控制。
- `todo.md`：具体待办事项列表，记录每个阶段的任务和状态。
- `reports/SOURCE_MANIFEST.md`：题面、附件、资料库和对标论文的来源与处理状态。
- `reports/QUESTION_COVERAGE.md`：顶层问题、边界条件、情景、指标、图表和验证的覆盖矩阵。
- `data/data_manifest.json`：数据快照、哈希、单位和允许派生操作。
- `reports/RESOURCE_BASELINE.md`：仅当题面含计算复杂度、存储、时间、成本、能耗或资源利用率目标时创建；记录可复现基线、候选方案、单位、质量约束和帕累托选择证据。

## 工作流

### 1. 询问用户偏好 AskUserQuestions

在规划前，只询问会实质影响流程的问题。问题要少而关键。

优先询问（按重要性排序）：

1. **排版引擎**：Typst 还是 LaTeX？— 决定 5writing 使用哪套模板和编译命令。两套引擎均覆盖全部模板（14 中 + 3 英）。Typst 使用 `typst` 命令编译；LaTeX 使用 `xelatex` 命令编译（需跑两遍解决交叉引用）。
2. **竞赛类型**：国赛/华为杯/华中杯/MCM/...— 决定模板选择，见 5writing 的模板族清单。
3. **论文语言**：中文/英文 — MCM/ICM/COMAP 强制英文，其他默认中文。
4. **子问题数量是否已知**：影响章节文件生成数量。若未知，由 2analysis-modeling 阶段根据题面确定。

将用户的选择记录到 `plan.md` 的"方案"小节中。


### 2. 制定方案

按以下结构编写 `plan.md`：

```markdown
# 方案

要依次调用这些 skill，按照里面要求完成任务。

用户偏好：
- 排版引擎：<Typst / LaTeX>
- 竞赛类型：<国赛 / 华为杯 / MCM / ...>
- 论文语言：<中文 / 英文>
- 子问题数量：<已知 N 个 / 待分析确定>
- 资料范围：<题面/附件/优秀论文目录/全部相关资料>
- 结果根目录：<实际绝对路径>
- 对标论文：<代表性论文及选择理由>
- 资源目标：<无 / 题面原文的计算、存储、时间、成本或能耗指标；基线定义>

workflow:
   step      skills
1. 赛题分析与建模设计 - `2analysis-modeling`
2. 编程实现和图表生成 - `3coding-visual`
3. 流程与架构图绘制 - `4drawio`
4. 竞赛论文撰写 - `5writing`
5. 验证和验收 - `6verity`
```

## 项目目录结构

各阶段按此骨架创建和填充文件：

```text
.
├── plan.md                      # 1: 本文件
├── todo.md                      # 1: 待办事项
├── reports/                     # 各阶段文档报告
│   ├── ANALYSIS_MODELING_REPORT.md  # 1: 赛题分析-建模报告（2analysis-modeling）
│   ├── SOURCE_MANIFEST.md           # 1: 题面、附件和对标资料证据清单
│   ├── QUESTION_COVERAGE.md         # 1: 子问题条件、情景、指标和验证覆盖矩阵
│   ├── RESOURCE_BASELINE.md          # 1/2: 资源优化题的基线、候选与帕累托证据
│   ├── RESULTS_REPORT.md            # 2: 结果报告（3coding-visual）
│   ├── DRAWIO_REPORT.md             # 3: 非数据图说明（4drawio）
│   ├── VERIFY_REPORT.md             # 5: 验收报告（6verity）
├── data/                        # 1/2: 原始数据快照和数据契约
│   └── data_manifest.json
├── code/                        # 2: 代码（3coding-visual）
│   ├── problem1.py
│   ├── problem2.py
│   ├── problem3.py               # 问题的数量应该更具题目动态调整
│   ├── ... 
│   └── utils.py
├── results/                     # 2: 结果记录（3coding-visual）
├── figures/                     # 2+3: 所有图表（3coding-visual + 4drawio）
│   ├── *.pdf                    #     数据图 + 非数据图 PDF
│   ├── *.drawio                 #     非数据图源文件
├── paper/                       # 4: 论文（5writing）
│   ├── main.typ / main.tex      #     论文主文件（按用户选择的引擎）
│   └── sections/                #     各节文件（.typ 或 .tex）
```

方案必须明确每个阶段由哪个下游 skill 负责，以及该阶段应产出什么文件。

### 3. 生成待办

将 `todo.md` 写成阶段性 checklist，格式如下：

```markdown
# 待办事项

- [ ] 1. 赛题分析与建模设计 - `2analysis-modeling`
- [ ] 2. 编程实现和图表生成 - `3coding-visual`
- [ ] 3. 流程与架构图绘制 - `4drawio`
- [ ] 4. 竞赛论文撰写 - `5writing`
- [ ] 5. 验证和验收 - `6verity`
```

每完成一个阶段，都要更新 `todo.md` 中对应任务的状态。

### 4. 依次执行阶段

按以下顺序调用下游 skills：

| 阶段 | Skill | 作用 | 主要产物 |
| --- | --- | --- | --- |
| 赛题分析与建模设计 | `2analysis-modeling` | 解析题意、识别变量/约束/数据/评价指标，并建立数学模型、目标函数、约束条件和求解策略。 | `ANALYSIS_MODELING_REPORT.md` |
| 编程实现和图表生成 | `3coding-visual` | 实现可复现代码，运行实验，生成结果表和多种多样的图表。 | `code/`, `results/` ,  `RESULTS_REPORT.md`, `figures/图表` |
| 流程与架构图绘制 | `4drawio` | 在论文确实需要时，绘制方法流程图、架构图和非数据型概念图。 | `figures/*.drawio`, `figures/*.pdf`, `DRAWIO_REPORT.md` |
| 竞赛论文撰写 | `5writing` | 基于分析、建模、代码结果和图表撰写最终竞赛论文，并按章节直接插入图表。 | `paper/` |
| 验证和验收 | `6verity` | 检查可复现性、一致性、产物完整性、格式规范和提交就绪状态。 | `VERIFY_REPORT.md` |

## 阶段边界

- `3coding-visual` 负责生成所有依赖计算结果或实验输出的数据图表。
- `4drawio` 只负责概念图、算法流程图、架构图、路线图等非数据型图示。
- 不要让 `4drawio` 重复绘制 `3coding-visual` 已经生成的统计图或数据图。
- `5writing` 负责决定图表在论文中的位置，并按所选引擎写入图表代码：
  - Typst：`#figure(image("../../figures/xxx.pdf", width: 85%), caption: [...])`
  - LaTeX：`\begin{figure}[H]\centering\includegraphics[width=0.85\textwidth]{../../figures/xxx.pdf}\caption{...}\label{fig:xxx}\end{figure}`
- 不要让 `5writing` 编造数值结论。论文中的数值必须来自 `RESULTS_REPORT.md`、结果表或已生成图表的数据。

## 启动前质量闸门（升级要求）

在调用下游 Agent 前，必须完成一次可审计预检，并把结论写入 `plan.md`：

1. **题目契约**：确认题目原文、顶层子问题数量、每个小问的输出对象，以及是否包含附件数据。若题面或附件不可读，必须标记为 `blocked_input`，不得让模型自行补造字段。
2. **数据契约**：为每份输入建立 `data/data_manifest.json`，记录原始文件名、来源 URL/附件标识、抓取或接收时间、SHA-256、单位、行列数、缺失率和允许的派生操作。时间序列必须声明训练、验证、回放区间。
3. **模型契约**：`ANALYSIS_MODELING_REPORT.md` 必须为每个子问题写出目标、变量、假设、约束、评价指标、失败条件和最小可行基线。只写“使用某算法”不算通过。
4. **信息边界**：明确哪些值是赛时可知、哪些是事后回放、哪些是代理变量。任何代理口径都必须出现在摘要、数据章节和结论限制中。
5. **阶段状态**：只有 `analysis_passed` 才能进入代码阶段；只有 `code_passed`（至少一次成功执行、结果文件存在、图表路径可解析）才能进入写作阶段；任一阶段失败都必须阻断下游并留下错误报告。
6. **资料证据**：`SOURCE_MANIFEST.md` 中每个声明为“已查看”的来源必须有本地快照或可复核链接；选定的对标论文必须说明为什么能代表题目，而不是只按文件名选择。
7. **覆盖证据**：`QUESTION_COVERAGE.md` 的每个问题必须有至少一个可执行模型、一个结果对象和一个校验方法；存在 `gap` 时状态不得为 `analysis_passed`。
   对刚性链、车列、机械臂、绳索或分段曲线上的有限尺寸构件运动，校验方法必须覆盖实体碰撞、完整连续区间、路径接头连续性和全体构件的约束极值；端点或整数时刻快照不能单独作为通过证据。
8. **输出形态**：写作阶段的最终交付必须包含可编译的 `main.typ` 或 `main.tex` 及 PDF；`paper.md` 只能作为草稿或中间交换格式，不能单独标记为提交就绪。
9. **资源目标（条件闸门）**：若题面要求低复杂度、低存储、低时间、低成本、低能耗或资源优化，先在 `RESOURCE_BASELINE.md` 固定一个可执行基线（算法/参数/数据切分、资源单位、质量指标和运行命令），再列出全部候选的“质量约束--资源指标”表。候选必须同时满足所有题设质量阈值，并在至少一项同单位资源上相对基线严格改善，才能标记 `resource_passed`。多目标题若存在不可避免的资源冲突，必须明确采用 `pareto_tradeoff`：逐项列出未改善的资源、数值、原因和适用边界；不得把它概括为全维度优化。不能把未运行的渐近式、只满足精度的方案、或只报告平均值而最坏情景失败的方案写成优化完成。若没有可行候选，状态为 `resource_gap`，必须阻断把该优化子问题写为完成。
10. **引擎状态**：所选 Typst/LaTeX 引擎可用却编译失败、超时或需未完成的交互安装时，验收状态必须是 `engine_failed`。可用其他渲染器做版式预览，但该 PDF 只能标为 `rendered_preview`，不得代替所选入口的“提交就绪”编译产物。

阶段之间只允许传递结构化结果，不允许把“错误文本”当作结果摘要。推荐使用如下最小契约字段：

```json
{
  "status": "success",
  "task": "ques1",
  "data_hashes": ["sha256:..."],
  "metrics": {"mae": 0.0, "rmse": 0.0},
  "artifacts": ["results/ques1.json", "figures/ques1.png"],
  "validation": {"independent_recompute": true, "time_split": "..."},
  "error": null
}
```

## 失败处理

失败必须是显式状态而不是自然语言占位：`blocked_input`、`invalid_plan`、`resource_gap`、`code_failed`、`engine_failed`、`verification_failed`。达到重试上限后立即停止当前子任务，保存错误、最后一次代码和输入哈希；禁止继续生成看似完整的论文。最终验收必须能从论文数值追溯到结构化结果文件，再追溯到数据快照。
