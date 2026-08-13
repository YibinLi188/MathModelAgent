---
name: 3coding-visual
description: "数学建模编程实现与数据图表生成阶段。根据 ANALYSIS_MODELING_REPORT.md 编写可复现代码、运行求解、验证约束、输出 RESULTS_REPORT.md 并生成论文可用的数据驱动图表 PDF。"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch
---

# 编程实现与数据图表生成

本 skill 承接 `2analysis-modeling`。目标是把 `reports/ANALYSIS_MODELING_REPORT.md` 里的模型和算法落实为可复现程序，跑出可信结果，并生成论文中需要的数据型图表。

## 数学建模规范参考

如需领域判断，读取 `../_references/math_modeling_norms.md` 中的“题型防错速查”“代码实现与结果”“编码阶段常见错误”和“图表与可视化”小节。该文件只作为规范知识库，不新增本阶段的固定产物。
结果字段和指标语义按 `../_references/result_contract.md` 执行。

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
  "schema_version": "1.1",
  "status": "success",
  "task": "ques1",
  "data_hashes": ["sha256:..."],
  "sample": {"n_total": 0, "n_train": 0, "n_validation": 0},
  "metrics": {"mae": 0.0, "rmse": 0.0},
  "resource": {
    "status": "resource_passed",
    "decision_rule": "strict_improvement | pareto_tradeoff",
    "quality_constraints": {"constraint_name": true},
    "baseline": {"id": "...", "run_command": "...", "metrics": {"runtime": {"value": 0.0, "unit": "s", "direction": "min"}}},
    "candidate": {"id": "...", "run_command": "...", "metrics": {"runtime": {"value": 0.0, "unit": "s", "direction": "min"}}},
    "comparison": {"strict_improvements": ["runtime"], "accepted_tradeoffs": [], "worst_case_scope": "..."}
  },
  "parameters": {},
  "artifacts": ["figures/ques1.png"],
  "validation": {
    "time_split": "train<=...; validation=...",
    "independent_recompute": true,
    "constraints_passed": true
  },
  "solution_evidence": {
    "feasibility_status": "feasible",
    "solver_converged": false,
    "termination_reason": "maximum function evaluations reached",
    "optimality_claim": "feasible_only",
    "restart_or_budget_checks": 3,
    "stability_evidence": "objective and constraint margins stable across three budgets"
  },
  "limitations": [],
  "error": null
}
```

`status=success` 的前提是代码至少成功执行一次、结果 JSON 可解析、声明的产物存在、约束检查通过，并完成一次独立重算或等价的结果复核。它只代表计算流程成功，不代表求解器收敛或最优。失败时使用 `status=failed` 并填写 `error`；失败结果不得交给 `5writing`。

每个 JSON 必须写 `solution_evidence`。优化器达到最大迭代/评估次数、数值异常或人工中止时，`solver_converged=false` 且 `optimality_claim=feasible_only`；即使硬约束全部通过也不得写成 `local_converged`。声明局部或全局最优时必须保存终止原因、最优性指标以及多初值/多预算证据；全局最优还需保存界、穷举或证明依据。

每个核心指标还必须有可审计的语义声明。推荐在结果 JSON 增加：

```json
{
  "metric_semantics": {
    "throughput_mbps": {
      "quantity": "successful_payload_rate",
      "unit": "Mbps",
      "numerator": "expected_successful_payloads",
      "concurrency_rule": "count_each_successful_object"
    }
  },
  "validation": {
    "independent_recompute": true,
    "independent_delta": 0.0,
    "tolerance": 1e-6
  }
}
```

题面含资源优化目标时，每个相关 JSON 必须补充 `resource` 对象，并遵循 `../_references/result_contract.md`。资源计数必须覆盖模型参数、预处理、压缩/解压、推理或求解中题面要求计入的部分；真实运行时间应记录机器、重复次数和统计量。候选不满足全部质量约束时不得拿它的资源数参与“最优”比较。只有同单位的严格改善可写入 `strict_improvements`。存储与编码/解码天然冲突时，用 `pareto_tradeoff` 逐项记录代价；没有严格改善、质量约束为假，或把未解释代价藏在汇总指标中，均标记为 `resource_gap`，不得交给写作阶段作为优化完成。

明确区分 `event_probability`（例如至少一个节点发送）、`successful_object_count`（例如成功数据包数）和 `throughput`。并发成功时不能把一个非空事件自动当成一个成功对象；必须保存单对象、双对象及期望成功对象数，或给出等价的逐对象计数证明。仿真统计也必须使用同一计数口径。

若分析阶段给出了“可比口径矩阵”，为每个主口径保存 `comparison_semantics`，并至少运行两个合理口径或一个口径加理论上/下界。图表和结果表必须把不同口径分列，不得把表面模型、分母或采样单位不同的参考结果直接计算相对误差。

执行优化前，将 `optimization_domain` 写入结果 JSON：变量名、类型、上下界、开/闭边界、可行组合来源、插值/外推策略和安全约束必须可机读。开边界用 `exclusive=true` 表示，不得为了方便求解器而改成闭边界；若实现采用网格近似，记录网格步长、最优点到边界的距离和至少两档更细网格的稳定性。代理模型按实体、组合、站点、患者或时间块分组切分；训练/验证/测试的分组键不得重叠，并输出重叠计数为0。

对结构零生成布尔观测掩码，并在结果 JSON 保存 `structural_zero_semantics`、`observed_count` 与 `structural_zero_count`。任何由均值、分位数、损耗率或概率进入目标函数/约束的统计量，必须断言其分母只含有效观测；至少用一个“把结构零误当观测”的反例测试证明闸门会报警。

成分/份额数据须保存 `compositional_audit`：原始行和、有效区间、剔除行、闭合规则、零语义、零替换或检测限、log-ratio 变换、分组键和替换敏感性。若输出亚类，另存 `cluster_stability`，至少含候选 $k$、实体级重采样方案、ARI/共聚类分布、成员清单及 `claim_level=stable|exploratory`。若输出类别网络差异，保存 `network_difference_audit`，并断言检验矩阵、绘图矩阵、预处理和统计量哈希/数值一致；至少构造一次“检验 Pearson 矩阵却展示偏相关矩阵”的反例并拒绝。

跨期优化须保存 `state_transition` 及逐期 `state_trace`，至少含期号、期初状态、流入、流出、期末状态和约束裕度。独立复算不得只比目标值；要从原始决策变量重放全部状态转移，并逐期检查容量、库存、守恒和终端约束。

物理动力学实现须在结果 JSON 保存 `coordinate_convention`、`equilibrium_definition`、`component_inertia_audit` 与 `physical_residuals`。组合刚体的惯量审计至少列构件、质量分配、质心、参考轴、自身惯量和平行轴项；代码应检查各项非负且总质量一致。若题面允许多种几何解释，运行主口径与至少一个替代口径，保存状态量和目标值敏感性，禁止挑选最接近参考答案的口径后删除其余结果。

线性受迫振动应尽可能同时生成频域和时域稳态结果，并保存关键幅值/平均功率差；非线性或时变系统至少保存全程功--能平衡残差。耗散元件必须断言瞬时耗散功率不为负。使用线性化、谐波平衡、代理或等效阻尼搜索时，候选必须再送入原微分方程和原目标函数；结果 JSON 同时保存近似值、原方程值和差异。

几何光学/辐射/视线模型须保存 `ray_geometry_audit`，至少含 `coordinate_convention`、`incident_direction_semantics`、`reflection_residual_max`、`source_angular_model`、`emitter_sampling`、`occlusion_intersection`、`receiver_geometry`、`receiver_intersection`、`efficiency_denominators` 和 `grid_refinement`。有限光源或接收面不得被静默退化为中心光线/点接收器；使用代理效率搜索时，保存代理值和原光线回放值，最终功率与可行性只能取原光线回放。网格加密须同时改变发射面和光源角采样，报告核心指标最大相对变化；缺少几何边界例或反射定律残差时不得标记 `status=success`。

空间覆盖/路径规划模型须保存 `spatial_coverage_audit`，至少含 `domain_geometry`、`candidate_geometry`、`coverage_kernel`、`boundary_clipping`、`overlap_denominator`、`search_grid`、`final_replay_grid`、`uncovered_metric`、`excess_overlap_metric`、`candidate_family` 与 `optimality_scope`。粗筛、插值代理或平均参数产生的指标不得直接进入论文；最终总长度、漏测率、重复覆盖及可行性必须由原始空间数据回放生成。须保留至少一个被完整回放拒绝的候选或等价负例，并验证边界、空交集、全覆盖和网格加密情形；缺少原网格回放或把有限候选族写成全局最优时不得标记 `status=success`。

连续构件运动模型须保存 `continuous_body_geometry_audit`，至少含 `path_parameterization`、`direction_convention`、`body_geometry`、`connector_geometry`、`adjacent_contact_rule`、`collision_kernel`、`path_segments`、`junction_continuity_residuals`、`coarse_scan_interval`、`critical_event_bracket`、`continuous_refinement`、`full_interval_clearance`、`constraint_propagation`、`extremum_scope`、`extremum_tolerance` 与 `coactive_components`。碰撞须对有限尺寸实体而非仅中心点/连接点判断；首次事件须保存临界前后符号相反的间隙或等价证据。对所有构件传播速度/加速度约束，并在全路径连续细化极值；容差内并列极值须保留全部活动构件，不能只保存 `argmax` 的第一个/最后一个索引。仅整数时刻、单一终点或代表构件检查不得标记 `status=success`。路径优化还须保存固定端点/可移动切点等自由度语义，避免把不同可行域的长度直接比较。

内生决策响应模型须保存 `decision_response_audit`，至少含 `decision_variable`、`response_variable`、`assignment_mechanism`、`confounders`、`identification_design`、`identification_assumptions`、`response_semantics`、`decision_bounds`、`boundary_hit_rate`、`response_scenarios` 和 `robust_replay`。若 `identification_design=observational_only`，输出只能标记为关联预测或情景优化，不得标记因果最优。至少运行一组响应系数扰动和一组时间/实体外回测；最优决策大量贴边而未扩大/解释安全域，或仅在训练内报告拟合优度时，不得标记 `status=success`。

边界候选须保存向可行域内部的扰动表。若近似目标形成等价脊/参数带，输出带的范围和可辨识性说明；若约束外候选看似更优，必须保留为负面测试并断言闸门拒绝。优化器返回值经过静默裁剪、四舍五入到边界或只在代理目标上更优时，`optimality_claim` 不得超过 `feasible_only`。

逆问题、定位、反演、编队和标定结果须在每个相关 JSON 保存 `identifiability_audit`，至少包含 `unknown_dimension`、`independent_observation_dimension`、`gauge_transformations`、`anchors_or_priors`、`jacobian_rank`、`smallest_singular_value`、`condition_number`、`discrete_ambiguity_count` 和 `invariance_negative_tests`。代码必须验证锚定后的雅可比达到声明秩，并实际运行至少一个平移/旋转/尺度/镜像/标签置换负例；若负例仍满足观测且未由锚点或先验排除，结论只能是等价类或多解。不得以残差近零、方程数较多或求解器 `success` 代替可辨识性证据。

声称多轮迭代调整或控制收敛时，须保存 `iteration_history`，逐轮记录选择集合、目标/残差、最大状态更新、约束裕度和终止原因；至少运行两个不同初值或扰动规模。生成一张真实迭代曲线或逐轮表，并将其列入 `artifacts`。只保存初态与终态时不得写“经多轮收敛”，只能写“联合批处理回放可行”。

题目提供 Excel/CSV 结果模板时，最终产物必须由保留模板结构和样式的表格引擎写入。写后重新导入，对每个可写区域逐格比对结构化结果；同时检查工作表名、固定说明、公式、合并区域和非填写单元未变化。范围收缩、错列、四舍五入差异或模板公式被覆盖均为失败，不能只凭“文件能打开”放行。

### Step 3.2：数据和时间序列闸门

运行前生成 `data/data_manifest.json`，记录来源、接收时间、SHA-256、字段单位、行列数和缺失率。训练/验证/回放按时间先后切分，禁止随机打乱时序样本。标准化、缺失填补和目标编码只能在训练集拟合，再应用于验证集；代码必须打印实际切分边界和有效样本量。样本少于参数量的模型不得作为主模型，除非报告明确降级并解释原因。

### Step 3.3：独立复核

代码完成主计算后，必须用独立函数、独立参数重建或保存的中间表重新计算至少一个核心指标和一个关键结论。两次结果的绝对差必须写入 JSON；超过 `1e-6`（或报告中声明的数值容差）则标记 `verification_failed`。

独立复核不得只是再次调用同一个生成函数或读取论文中的硬编码数字。至少保留一个纯函数/中间表 oracle，并对边界场景执行测试：单节点、两个对象并发成功、两个对象并发失败、零丢包和最大题面丢包。随机仿真应记录完整种子列表、重复次数、样本标准差或置信区间、运行时长以及 Python/依赖版本。

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

图表生成结束后，检查每个图表的源数据、单位、参数筛选条件和随机种子是否能回到结果 JSON；没有来源记录的图表不得交给写作阶段。

### Step 5：交接阻断

代码阶段结束前，逐个检查 `results/*.json`。任何子问题缺少结果文件、数据哈希、样本量、验证记录或图表路径时，必须阻断写作阶段，并在 `reports/RESULTS_REPORT.md` 中给出可操作的修复项。题面有资源目标时，缺少可运行基线、资源单位、最坏情景资源汇总或严格改善证据同样必须阻断写作阶段。写作手只能读取通过闸门的结构化结果，不能从自然语言错误日志猜测数值。
