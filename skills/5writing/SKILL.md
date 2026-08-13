---
name: 5writing
description: "数学建模竞赛论文撰写阶段，支持 Typst 和 LaTeX 双引擎。根据 ANALYSIS_MODELING_REPORT.md、RESULTS_REPORT.md 和 figures/*.pdf 选择比赛模板、排版引擎、组织章节，并在论文正文中按章节直接插入图表。"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch
---

# 竞赛论文撰写（Typst / LaTeX）

本 skill 承接 `3coding-visual` 和 `4drawio`。前序阶段只提供真实数据、图表 PDF 和记录文件；本阶段负责选择比赛模板和排版引擎、组织论文结构，并决定每张图表放入哪个章节。

**Typst 引擎**下可调用 typst-author skill 学习 typst 写法；**LaTeX 引擎**参考本文件末尾的"LaTeX 写作要点"小节。

## 数学建模规范参考

如需领域判断，读取 `../_references/math_modeling_norms.md` 中的“论文写作”“图表与可视化”和“非数据图工具选择”小节。该文件只作为规范知识库，论文结构仍按比赛模板和当前赛题内容决定。

## 模板族

本技能内捆绑的模板位于：

```text
templates/zh/<竞赛>/main.typ         # Typst 模板
templates/zh/<竞赛>-latex/main.tex   # LaTeX 模板
templates/en/<竞赛>/main.typ         # Typst 模板
templates/en/<竞赛>-latex/main.tex   # LaTeX 模板
```

**LaTeX 模板覆盖范围**：所有中文模板和英文模板均已提供 LaTeX 版本（`-latex` 后缀），使用 xelatex 编译。

支持的中文模板（Typst + LaTeX 双版本）：

```text
apmcm, changsanjiao, cumcm, default, diangongbei, dongsansheng,
huashubei, huaweibei, huazhongbei, mathorcup, mcm, shuweibei, stats, wuyibei
```

华为杯、华中杯、五一杯统一使用 `huaweibei`、`huazhongbei`、`wuyibei` 作为模板。

支持的英文模板（Typst + LaTeX 双版本）：

```text
apmcm, default, mcm
```

论文中的所有数值图表结论必须来自 `results/*.json`、`reports/RESULTS_REPORT.md` 或 `figures/*`。优先从结构化结果 JSON 取值，不得编造、估算或使用不同的四舍五入方式；正文数字必须能追溯到数据哈希和代码运行记录。

最终交付不是只有 Markdown 草稿。必须保留所选引擎的 `main.typ` 或 `main.tex`，成功编译 PDF，并在验收阶段渲染检查。`paper.md` 可以作为中间交换格式，但不能在没有可编译入口和 PDF 的情况下标记为“完整论文”或“提交就绪”。


## 工作流

### 步骤 0：确定排版引擎

**撰写论文前必须让用户选择排版引擎。** 引擎决定后续所有步骤（模板路径、章节文件扩展名、图片插入语法、编译命令），选错会导致整篇论文格式错误。

使用 AskUserQuestion 工具向用户询问："撰写论文使用哪种排版引擎？"

- 选项 1：LaTeX（xelatex 编译，数学建模竞赛主流，模板已全部就绪）— 推荐选项放第一位
- 选项 2：Typst（typst 编译，调用 typst-author skill 辅助写作）

询问前先读取 `plan.md` 的"用户偏好 → 排版引擎"字段作为预选项：
- 若 plan.md 已记录引擎选择，向用户确认："检测到之前选择的引擎是 <LaTeX/Typst>，是否沿用？"
- 若 plan.md 不存在或未记录引擎选择，直接询问用户选择。
- 若用户未明确指定或跳过，**默认使用 LaTeX**。

根据确定的引擎选择对应模板族：

- **Typst 引擎**：使用 `templates/<lang>/<竞赛>/main.typ`，调用 typst-author skill。编译命令 `typst compile main.typ`。
- **LaTeX 引擎**：使用 `templates/<lang>/<竞赛>-latex/main.tex`，xelatex 编译（中文和英文均需跑两遍解决交叉引用）。编译命令 `xelatex -interaction=nonstopmode main.tex`（执行两次）。

**后续步骤中的所有代码示例、文件扩展名、图片插入语法都必须按所选引擎选择对应版本，不要混用。**

### 步骤 1：选择语言和模板


除非用户明确要求中文，否则 MCM/ICM/COMAP 一律使用英文。所有中文竞赛名称使用中文。

模板键示例（Typst 引擎）：

```text
长三角 -> zh/changsanjiao
APMCM 英文版 -> en/apmcm
全国赛/国赛/CUMCM -> zh/cumcm
统计建模 -> zh/stats
MCM/ICM/COMAP -> en/mcm
```

模板键示例（LaTeX 引擎）：

```text
全国赛/国赛/CUMCM -> zh/cumcm-latex
MCM/ICM/COMAP -> en/mcm-latex
```

### 步骤 2：准备模板

用以下命令检查捆绑模板是否可访问（`SKILL_DIR` 为本 skill 所在目录）：

**Typst 模板**：

```bash
ls "$SKILL_DIR/templates/zh/<竞赛>/main.typ" 2>/dev/null && echo "OK" || echo "MISSING"
```

- **文件存在（OK）**：直接将 `templates/zh/<竞赛>/` 整目录复制到 `paper/`。这些模板是自包含入口文件，不依赖额外共享样式文件。
- **文件不存在（MISSING）**：说明 skill 未完整安装或在沙箱中，此时依照本 SKILL.md 步骤 3 列出的对应节文件结构，从零重建最小可编译 Typst 框架，并在 `paper/` 内注明"重建自 default 结构"。

存在匹配模板时，绝不从零开始写论文。

**LaTeX 模板**：

```bash
ls "$SKILL_DIR/templates/zh/<竞赛>-latex/main.tex" 2>/dev/null && echo "OK" || echo "MISSING"
```

- **文件存在（OK）**：将 `templates/zh/<竞赛>-latex/` 整目录复制到 `paper/`。
- **文件不存在（MISSING）**：说明 skill 未完整安装或在沙箱中，此时依照本 SKILL.md 步骤 3 列出的对应节文件结构，从零重建最小可编译 LaTeX 框架，并在 `paper/` 内注明"重建自 default-latex 结构"。


### 步骤 3：构建图表规划

在写正文各节之前，根据 `figures/*.pdf`、`reports/RESULTS_REPORT.md`，以及 `reports/DRAWIO_REPORT.md`（如果存在）构建图表规划：

```text
图表规划
fig_roadmap.pdf -> 引言/问题重述
fig_flow_q1.pdf -> 问题一模型构建
fig_flow_q2.pdf -> 问题二模型构建
fig_pipeline.pdf -> 数据预处理/方法节
结果图 -> 对应的结果节
```

图片路径相对于写入该图片的文件：写在 `paper/main.typ` 或 `paper/main.tex` 中通常用 `../figures/xxx.pdf`，写在 `paper/sections/*.typ` 或 `paper/sections/*.tex` 中通常用 `../../figures/xxx.pdf`。

**Typst 引擎**图片插入：

```typst
#figure(
  image("../../figures/fig_q1_error_dist.pdf", width: 85%),
  caption: [问题一预测误差分布],
)
```

**LaTeX 引擎**图片插入：

```latex
\begin{figure}[H]
  \centering
  \includegraphics[width=0.85\textwidth]{../../figures/fig_q1_error_dist.pdf}
  \caption{问题一预测误差分布}
  \label{fig:q1_error}
\end{figure}
```

英文论文使用英文图注。

每一张结果图都必须直接嵌入对应章节，并在正文中有题注、编号和至少一段解释。只写 `figures/foo.png` 或反引号路径不算引用；图片路径必须能从入口文件解析。图表规划还要标明其数据来源 JSON、参数筛选和对比目的。

### 步骤 4：撰写各节

**以下章节文件名按所选引擎使用 `.typ`（Typst）或 `.tex`（LaTeX）扩展名。** 例如 Typst 引擎用 `1_restatement.typ`，LaTeX 引擎用 `1_restatement.tex`。文件名主体保持一致。

中文数学建模通用模板各节文件（`changsanjiao`、`diangongbei`、`huashubei`、`mathorcup`、`wuyibei`）：

```text
1_restatement.typ  - 问题重述与分析
2_analysis.typ     - 数据理解与总体思路
3_assumptions.typ  - 模型假设
4_symbols.typ      - 符号说明
5_problem1.typ     - 问题一建模与求解
6_problem2.typ     - 问题二建模与求解
7_problem3.typ     - 问题三建模与求解
...         - 根据题目调整问题数量  
8_evaluation.typ   - 灵敏度分析、模型评价与推广
A_code.typ         - 附录代码
```

国赛/华中杯/华为杯（`cumcm`、`huazhongbei`、`huaweibei`）按以下章节结构：

```text
1_restatement.typ
2_analysis.typ
3_assumptions.typ
4_symbols.typ
5_problem1.typ
6_problem2.typ
7_problem3.typ
...        - 根据题目调整问题数量
8_sensitivity.typ
9_evaluation.typ
A_code.typ
```

东三省模板（`dongsansheng`）额外使用单独摘要文件：

```text
abstract.typ
1_restatement.typ
2_analysis.typ
3_assumptions.typ
4_symbols.typ
5_problem1.typ
6_problem2.typ
7_problem3.typ
...       - 根据题目调整问题数量
8_evaluation.typ
A_code.typ
```

数维杯模板（`shuweibei`）保留原 LaTeX 的示例入口命名：

```text
Abstract.typ
Introduction.typ
2_analysis.typ
3_assumptions.typ
4_symbols.typ
5_problem1.typ
6_problem2.typ
7_problem3.typ
...      - 根据题目调整问题数量
8_evaluation.typ
Appendices1.typ
A_code.typ
```

中文默认模板（`default`）：

```text
1_restatement.typ
2_assumptions.typ
3_symbols.typ
4_problem1.typ
5_problem2.typ
6_problem3.typ
...      - 根据题目调整问题数量
7_sensitivity.typ
8_evaluation.typ
A_code.typ
```

中文统计建模各节文件：

```text
1_introduction.typ
2_method.typ
3_data.typ
4_analysis.typ
5_results.typ
6_conclusion.typ
A_code.typ
```

英文 MCM/APMCM 各节文件（`en/mcm`、`en/apmcm`、`zh/mcm`、`zh/apmcm`）：

```text
1_introduction.typ
2_assumptions.typ
3_model_design.typ
4_solution.typ
5_sensitivity.typ
6_strengths_weaknesses.typ
7_conclusions.typ
A_code.typ
```

**LaTeX 模板章节文件**（对应 `-latex` 后缀模板，结构与 Typst 版本一一对应）：

国赛 LaTeX 模板（`zh/cumcm-latex`，对应 `cumcm` Typst 版本）：

```text
1_restatement.tex
2_analysis.tex
3_assumptions.tex
4_symbols.tex
5_problem1.tex
6_problem2.tex
7_problem3.tex
8_sensitivity.tex
9_evaluation.tex
A_code.tex
```

MCM/ICM LaTeX 模板（`en/mcm-latex`）：

```text
1_introduction.tex
2_assumptions.tex
3_model_design.tex
4_solution.tex
5_sensitivity.tex
6_strengths_weaknesses.tex
7_conclusions.tex
A_code.tex
```

其余 LaTeX 模板（`changsanjiao-latex`、`default-latex`、`huashubei-latex`、`mathorcup-latex`、`wuyibei-latex`、`huazhongbei-latex`、`huaweibei-latex`、`diangongbei-latex`、`dongsansheng-latex`、`shuweibei-latex`、`stats-latex`、`apmcm-latex`、`mcm-latex`、`en/apmcm-latex`、`en/default-latex`）的章节文件命名与上述结构类似，以 `main.tex` 中 `\input{}` 引用的文件名为准。

英文默认模板（`en/default`）：

```text
1_introduction.typ
2_assumptions.typ
3_notations.typ
4_model.typ
5_sensitivity.typ
6_evaluation.typ
7_conclusions.typ
A_code.typ
```

**正文写作应使用连贯的学术段落。避免在最终论文中出现工作流内部名称，如 `reports/`、`figures/` 或 `CLAUDE.md`。**

按 `QUESTION_COVERAGE.md` 逐项写作。每个顶层问题至少包含问题分析、假设、符号、模型推导、数值求解、仿真验证、误差解释和局限；复杂拓扑或参数范围必须用情景表/参数扫描呈现，不能只给单一基准数字。对标优秀论文时，单独给出参考论文的选择依据和可验证差距，不得把参考论文的数值或文字改写成自己的实验结果。

## 完整论文深度闸门

不要把能编译的“实验简报”标记为完整优秀论文。每篇准备交付或参与优秀论文对标的稿件必须在编译前完成以下检查，并将证据写入验收报告：

- 入口文件必须有问题重述、问题分析、假设、符号、每个顶层问题的方法与求解、敏感性或稳健性、模型评价、参考文献和可复现实验附录；不能把多个顶层问题压缩成一段结论。
- 每个顶层问题必须给出输入--输出定义、至少一个可执行算法步骤或伪代码、完整约束/目标、逐组或逐情景结果表、基线与候选的可比指标，以及失败情景或局限。资源题还必须逐项列出资源单位、最坏情形和取舍。
- 每个顶层问题若包含阈值、秩、采样规则、模型族或求解器等可选参数，必须各自将最终方案与至少一个合理但可能失败的替代方案放在同一质量和资源口径下比较；不得只在另一子问题展示消融，或只展示最终方案的内部参数。选择结论须由该消融/对照结果支持。
- 对标论文的核心数字冲突时，正文必须先列出表面/对象模型、分子、分母、权重、采样单位、边界和不确定性，再比较定义一致的子集。不同口径只能写成“口径敏感性”，不得挑选最接近的数字冒充正确性验证。
- 物理动力学题首次给出惯量或恢复项时，正文必须能看出构件清单、坐标/转轴、质心与平行轴口径；若合理几何解释会改变结论，须给口径敏感性，不得只报最终惯量。线性受迫振动应展示频域--时域交叉验证或功--能残差；含近似/代理目标的优化要把“筛选近似”和“原方程最终验收”分开叙述。
- 几何光学、辐射传输或视线覆盖题首次报告效率时，正文必须说明入射/反射方向、有限光源角分布、发射面采样、遮挡相交、接收面几何和效率分母，并给反射定律残差及网格加密误差。中心光线、点接收器或距离经验式只能写成筛选近似；若最终候选未在有限光源、有限发射面和有限接收面上回放，不得把效率或功率写成验收值。
- 空间扫描、测线、设施布设或区域覆盖题首次报告方案时，正文必须说明覆盖域、候选几何、覆盖核、边界裁剪、漏测与重叠分母，以及最终回放网格。总长度、漏测率、超阈值重叠须分列，不能只给加权目标；粗网格或平均参数只能写成筛选近似。若搜索限于平行线、固定航向、人工分区或离散候选，摘要和结论必须使用“该候选族内最优”或“可行近似解”，不得省略最优性范围。
- 历史价格、促销、治疗、政策等内生决策变量用于优化时，正文必须区分观测相关、预测和因果响应，并披露识别设计、共同原因、决策范围、响应情景和边界命中率。没有可信干预识别时，不得把回归弹性或相关斜率写成因果规律或“最优价格/剂量/政策”；只能写条件情景方案，并给时间/实体外验证和参数敏感性。大量决策贴边必须在摘要或局限中显式警告。
- 闭边界最优必须在首次报告时同句注明边界激活，并给至少一个向内扰动证据；等效参数带或弱可辨识性存在时，优先报告可接受带与条件，不能把优化器偶然返回的一点写成唯一物理参数。代理或等效模型越界的更优点只能作为判废反例。
- 优化结果必须按 `solution_evidence` 用词：`feasible_only` 只能写“可行近似解/方案”；只有 `local_converged` 才能写“局部收敛解”；“全局最优”只允许来自 `global_proven`。摘要与结论同样受此限制。
- 抽样验收题首次给出样本量时，正文必须同时写明假设方向、I/II 类错误业务含义、显著性、效应点和功效、整数接受/拒绝域及未决区；若效应点/功效来自补充假设，摘要和结论必须称“条件设计”，不得称题面唯一最少样本量，也不得把“不拒绝”改写为接受相反命题。
- 检测、拆解、返工或退换题首次给出利润/策略时，必须在同一节交代利润分子分母、收入次数、逐轮成本、装配缺陷条件概率、拆解后潜在质量如何继承以及终止性证据。批次利润、单件交付利润和单轮利润不得直接算相对误差或并列排名；局部搜索、有限预算仿真与全策略穷举须分层标注。
- 对优化题，在首次报告结果的同一段内写清证据层级：实测最优、观测域插值最优、代理模型域内最优或外推候选四者不得混写。严格不等式的结果必须注明边界不取到；若只有上确界，先写“无最大值”，再把工程裕度点单列为建议，不得把网格最靠近边界的点包装成解析最优。新增实验表至少包含“工况、信息目标、依据、验证/判废准则”四列。
- 结构零（未观测/未运输/不适用）不得在正文中写成真实的 0 值。首次使用相关统计量时同句说明零值语义、有效样本数和处理规则；若优秀论文或基线使用不同零值口径，只能列为口径敏感性。
- 成分/份额数据首次建模时须说明闭合、非检出/零替换、log-ratio 坐标和替换敏感性；不得把闭合原比例的普通相关直接写成成分关联。聚类结果须同时给具体成员和实体级稳定性；稳定性不过闸门时，用“探索性亚类/局部簇”，不得用“最优三类”“分类真实可靠”等确定措辞。网络差异的正文结论必须引用与热力图完全相同矩阵的整体检验；不拒绝原假设只能写“证据不足”，不能写“两个网络相同”。
- 跨期计划首次给出结果时必须同时展示状态转移口径和前缀可行性：至少列逐期流入、流出、期末库存/状态、最小裕度与压力测试。只给全部周期总量、平均值或最终库存不足以支持“全期可行”。若“最少供应商数/最大产能”依赖预测分位数、置信水平或初始库存，摘要必须将数值与情景绑定。
- 题目要求提交结果模板时，附录须给出模板写回范围、逐格复核数量和模板结构未改变的证据；正文只引用已通过回写验收的附件，不得引用临时 CSV 或手工复制表。
- 结果图必须服务于不同的论证目的：质量约束、资源比较和敏感性/失败情景至少各有一项证据；同一张图不能重复充当三类证据。
- 机械、几何或多自由度物理题的图表规划至少包含一张受力/坐标/构件关系图和一张数据响应图；若转轴、质心、力臂或符号方向决定方程，却只有时间曲线而没有物理示意，深度闸门应返回补图。题面指定多个报告时刻时，正文须完整列出或用明确分表覆盖，不能只展示一个代表时刻再声称已覆盖全部要求。
- 定位、标定、反演、SLAM 或编队等逆问题首次声称唯一坐标/参数前，正文必须列出观测不变的平移、旋转、尺度、镜像或标签置换，并说明锚点、先验或身份规则如何逐项消除。至少报告锚定后雅可比秩及一个条件性指标，并展示一个未锚定/退化几何负例；“方程数大于未知数”或残差接近零不能作为唯一性证明。
- 论文若把方案描述为“多轮迭代收敛”，正文必须展示真实 iteration history 的曲线或逐轮表，至少含残差/目标、最大状态更新和停止原因，并给两个初值或扰动情景。只有调整前后两张图时，措辞只能是“联合回放后的可行结果”，不得虚构中间轮次或收敛速度。
- 附录必须给出复现所需的输入清单/哈希摘要、运行环境、运行命令、独立复算方法和关键算法或完整代码的可定位入口。不得将内部工作流文件路径写进论文正文；附录可使用正式的“复现实验说明”表述。
- 不以页数凑篇幅，也不预设统一的最低页数；但若同题对标稿普遍含有算法、逐组实验和附录，而生成稿缺少这些实质证据，则判为深度不足，返回写作阶段扩写后重新编译和视觉检查。

验收报告须明确标记 `paper_depth=passed|failed`，逐项记录上述证据。`failed` 时不得进入下一题，也不得把 PDF 标为“完整论文”或“优秀论文”。

### 步骤 5：参考文献

只使用真实存在的参考文献。文件名按引擎选择：Typst 用 `paper/references.typ`，LaTeX 用 `paper/references.tex`。

**Typst 引擎**：

```typst
#set enum(numbering: "[1]")
#enum[
  作者. 题名[J]. 期刊名, 年份, 卷(期): 页码.
  Author. "Title." Journal or Conference, year.
]
```

正文上标引用：`相关研究已用于物流网络优化#super("[1]")。`

**LaTeX 引擎**：

```latex
\begin{thebibliography}{99}
  \bibitem{ref1} 作者. 题名[J]. 期刊名, 年份, 卷(期): 页码.
  \bibitem{ref2} Author. "Title." Journal, year.
\end{thebibliography}
```

正文引用用 `\cite{ref1}` 或 `\cite{ref1,ref2}`。

### 步骤 6：最后撰写摘要或总结

在所有章节完成后撰写中文摘要或英文 Summary Sheet。必须包含每个子问题的方法和精确的数值结果。

摘要只引用已经通过验证的结构化结果；任何 `gap`、`verification_failed` 或近似模型都必须在摘要、模型局限或结论中诚实标注。

## 升级后的交接规则

Writer 只能消费 `status=success` 的结构化代码结果，并必须继续读取 `solution_evidence` 限定措辞。若某个子问题为 `failed`、`resource_gap`、缺少数据哈希、缺少验证字段或图表路径不存在，应停止写作并在验收报告中记录，而不是用“结果待补充”填空。题面有资源目标时，正文必须同时写出基线、候选的质量约束、资源单位、最坏情景结果和严格改善幅度；只有 `resource.status=resource_passed` 的量才能使用“低复杂度”“显著降低”等完成性措辞。`decision_rule=pareto_tradeoff` 时必须同句给出未改善资源及代价，且不得写成全维度“最优”。图片语法必须与选定引擎一致：Markdown 使用 Markdown 图片，LaTeX 使用 `figure`/`includegraphics`，Typst 使用 `figure`/`image`；禁止把一种引擎的标签复制到另一种正文。

## LaTeX 写作要点

以下要点供 **LaTeX 引擎**使用。Typst 引擎请调用 typst-author skill 获取语法帮助。

### 编译命令

```bash
# 中文模板（xelatex，跑两遍解决交叉引用）
xelatex main.tex && xelatex main.tex

# 英文模板（xelatex，同样跑两遍）
xelatex main.tex && xelatex main.tex
```

### 文档结构

```latex
\documentclass[a4paper,12pt]{article}   % 英文
\documentclass[a4paper,12pt]{ctexart}   % 中文

\usepackage{...}   % 宏包加载
\usepackage{graphicx}   % 图片支持
\usepackage{booktabs}   % 三线表
\usepackage{amsmath,amssymb}   % 数学公式
\usepackage{hyperref}   % 交叉引用（需两遍编译）
```

### 图表插入

```latex
\begin{figure}[H]
  \centering
  \includegraphics[width=0.85\textwidth]{../../figures/fig_q1.pdf}
  \caption{图注}
  \label{fig:q1}
\end{figure}

% 三线表
\begin{table}[htbp]
  \centering
  \caption{表注}
  \begin{tabular}{ccc}
    \toprule
    \textbf{列1} & \textbf{列2} & \textbf{列3} \\
    \midrule
    数据 & 数据 & 数据 \\
    \bottomrule
  \end{tabular}
\end{table}
```

### 交叉引用

```latex
如图~\ref{fig:q1}所示，...   % 图片引用
式~(\ref{eq:objective}) 给出...   % 公式引用
见第~\pageref{fig:q1} 页   % 页码引用
```

### 数学公式

```latex
行内公式：$f(x) = \sum_{i=1}^n \theta_i \phi_i(x)$

行间公式：
\begin{equation}
  \mathcal{L}(\theta) = \frac{1}{N}\sum_{i=1}^N (y_i - \hat{y}_i)^2
  \label{eq:objective}
\end{equation}
```

### 章节和强调

```latex
\section{问题重述}
\subsection{问题背景}
\textbf{问题一：} xxx   % 对应 Typst 的 #strong
```
