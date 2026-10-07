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
储能、库存、滚动预测等跨期决策题同时按 `../_references/time_coupled_optimization_audit.md` 生成信息穿越测试、连续状态回放和官方附件重读证据。

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
  "schema_version": "1.2",
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

同时创建 `results/results_contract_manifest.json`，显式列出正式子问题契约；输入清单、审计明细、灵敏度原始表和门禁测试等辅助 JSON 不得混入清单：

```json
{
  "schema_version": "1.0",
  "contracts": [
    {"task": "ques1", "file": "ques1.json"},
    {"task": "ques2", "file": "ques2.json"}
  ]
}
```

清单中的 `task` 必须与目标 JSON 的 `task` 完全一致，文件路径必须位于 `results/` 内，任务和文件均不得重复。新增或删除顶层子问题时同步修改清单；禁止让验证器通过扫描目录猜测哪些 JSON 是正式结果。

`status=success` 的前提是代码至少成功执行一次、结果 JSON 可解析、声明的产物存在、约束检查通过，并完成一次独立重算或等价的结果复核。它只代表计算流程成功，不代表求解器收敛或最优。任何非空 `blocked*` 字段都表示仍有未解决前置事实，不得同时写 `status=success` 或 `validation.passed=true`。失败时使用 `status=failed` 并填写 `error`；失败结果不得交给 `5writing`。

每个 JSON 必须写 `solution_evidence`。优化器达到最大迭代/评估次数、数值异常或人工中止时，`solver_converged=false` 且 `optimality_claim=feasible_only`；即使硬约束全部通过也不得写成 `local_converged`。声明局部或全局最优时必须保存终止原因、最优性指标以及多初值/多预算证据；全局最优还需保存界、穷举或证明依据。

不要直接把求解库的 `success` 布尔值映射成业务成功。结构化保存原始状态码、消息、`termination_category`、是否存在 incumbent、目标值、有限界、gap 和 gap 容差；达到限制而有 incumbent 时，计算流程可为 `status=success`，但 `solver_converged=false`、`optimality_claim=feasible_only`。`global_proven` 仅在正常终止且有限 gap 不超过声明容差时允许。gap 为 `NaN/Infinity/null` 或缺少界时必须硬降级。

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

抽样决策实现须把 `sampling_decision_audit` 写入结构化结果：至少包含假设方向、$p_0$、效应点/先验或损失、alpha、beta/功效、样本量、整数接受/拒绝阈值、未决区和停止规则。对离散分布直接保存判定边界处及相邻点的精确尾概率，并生成操作特性数据；若使用正态或渐近近似，必须与精确二项/超几何 oracle 比较误差。缺少效应点或功效时，输出 `identifiability=conditional_design`，不得把搜索到的某个 $n$ 标成题面唯一最小值。

循环生产或返工代码须保存 `rework_state_audit`：状态枚举/编码、潜在质量继承规则、每类转移的概率与即时成本、收入触发、吸收状态、不可行策略数和终止性指标。解析模型至少检查 $(I-Q)V=c$ 残差并拒绝奇异/非吸收策略；仿真模型按策略和压力情景保存完成数、最大轮数命中数、平均循环数及共同随机数/种子。拆解后旧件质量不得被静默重抽样，`-inf`、未完成轨迹或最大轮数截断不得参与“最优”排序。

轮作/排班/多季资源代码须保存 `rotation_land_audit`：资源与子季索引、按真实日历排序的相邻边、历史边界状态、模式互斥、滚动窗口起止、混合子资源的状态继承口径，以及集中度/最小规模是硬约束、条件阈值还是事后审计。独立验证器必须从原始决策变量重算每期资源守恒、相邻禁配和每个滚动窗口覆盖；不能复用求解器约束对象充当验证。若模型可线性化，保存求解状态、上下界与 MIP gap；启发式结果须保存种群/候选域、可行率、修复规则、多种子分布和 `optimality_claim=candidate_only`。

对结构零生成布尔观测掩码，并在结果 JSON 保存 `structural_zero_semantics`、`observed_count` 与 `structural_zero_count`。任何由均值、分位数、损耗率或概率进入目标函数/约束的统计量，必须断言其分母只含有效观测；至少用一个“把结构零误当观测”的反例测试证明闸门会报警。

成分/份额数据须保存 `compositional_audit`：原始行和、有效区间、剔除行、闭合规则、零语义、零替换或检测限、log-ratio 变换、分组键和替换敏感性。若输出亚类，另存 `cluster_stability`，至少含候选 $k$、实体级重采样方案、ARI/共聚类分布、成员清单及 `claim_level=stable|exploratory`。若输出类别网络差异，保存 `network_difference_audit`，并断言检验矩阵、绘图矩阵、预处理和统计量哈希/数值一致；至少构造一次“检验 Pearson 矩阵却展示偏相关矩阵”的反例并拒绝。

跨期优化须保存 `state_transition` 及逐期 `state_trace`，至少含期号、期初状态、流入、流出、期末状态和约束裕度。独立复算不得只比目标值；要从原始决策变量重放全部状态转移，并逐期检查容量、库存、守恒和终端约束。

物理动力学实现须在结果 JSON 保存 `coordinate_convention`、`equilibrium_definition`、`component_inertia_audit` 与 `physical_residuals`。组合刚体的惯量审计至少列构件、质量分配、质心、参考轴、自身惯量和平行轴项；代码应检查各项非负且总质量一致。若题面允许多种几何解释，运行主口径与至少一个替代口径，保存状态量和目标值敏感性，禁止挑选最接近参考答案的口径后删除其余结果。

线性受迫振动应尽可能同时生成频域和时域稳态结果，并保存关键幅值/平均功率差；非线性或时变系统至少保存全程功--能平衡残差。耗散元件必须断言瞬时耗散功率不为负。使用线性化、谐波平衡、代理或等效阻尼搜索时，候选必须再送入原微分方程和原目标函数；结果 JSON 同时保存近似值、原方程值和差异。

几何光学/辐射/视线模型须保存 `ray_geometry_audit`，至少含 `coordinate_convention`、`incident_direction_semantics`、`reflection_residual_max`、`source_angular_model`、`emitter_sampling`、`occlusion_intersection`、`receiver_geometry`、`receiver_intersection`、`efficiency_denominators` 和 `grid_refinement`。有限光源或接收面不得被静默退化为中心光线/点接收器；使用代理效率搜索时，保存代理值和原光线回放值，最终功率与可行性只能取原光线回放。网格加密须同时改变发射面和光源角采样，报告核心指标最大相对变化；缺少几何边界例或反射定律残差时不得标记 `status=success`。

空间覆盖/路径规划模型须保存 `spatial_coverage_audit`，至少含 `domain_geometry`、`candidate_geometry`、`coverage_kernel`、`boundary_clipping`、`overlap_denominator`、`search_grid`、`final_replay_grid`、`uncovered_metric`、`excess_overlap_metric`、`candidate_family` 与 `optimality_scope`。粗筛、插值代理或平均参数产生的指标不得直接进入论文；最终总长度、漏测率、重复覆盖及可行性必须由原始空间数据回放生成。须保留至少一个被完整回放拒绝的候选或等价负例，并验证边界、空交集、全覆盖和网格加密情形；缺少原网格回放或把有限候选族写成全局最优时不得标记 `status=success`。

连续构件运动模型须保存 `continuous_body_geometry_audit`，至少含 `path_parameterization`、`direction_convention`、`body_geometry`、`connector_geometry`、`adjacent_contact_rule`、`collision_kernel`、`path_segments`、`junction_continuity_residuals`、`coarse_scan_interval`、`critical_event_bracket`、`continuous_refinement`、`full_interval_clearance`、`constraint_propagation`、`extremum_scope`、`extremum_tolerance` 与 `coactive_components`。碰撞须对有限尺寸实体而非仅中心点/连接点判断；中心距或包围圆只可粗筛候选对，最终须以包含真实长度、宽度和朝向的实体轮廓（如有向矩形分离轴）精确判定。首次事件须保存临界前后符号相反的间隙或等价证据。对所有构件传播速度/加速度约束，并在全路径连续细化极值；容差内并列极值须保留全部活动构件，不能只保存 `argmax` 的第一个/最后一个索引。仅整数时刻、单一终点或代表构件检查不得标记 `status=success`。路径优化还须保存固定端点/可移动切点等自由度语义，避免把不同可行域的长度直接比较。

连续串联构件沿单调径向曲线运动时，先由路径参数化核对头部运动方向，再确定后续节点的参数序关系；例如 `r=cθ(c>0)` 向中心盘入时头部 `θ` 递减，而位于外侧的后续节点 `θ` 必须逐点增大。任何求根无解、优化无可行解或执行警告都必须阻断成功状态，不得以缩半、置零、上一时刻值或其他回退数值继续计算。

含多根的距离方程须同时满足空间序关系与时间连续性：每个时刻从上一时刻的根连续延拓，不能独立扫描后取首个符号变化区间。括界须从当前参数用局部增量向允许方向扩张并锁定最近的符号变化，禁止反复乘大绝对参数上界跨过多个周期根。逐时输出必须复核相邻时刻位移与速度积分相容；即使每一列的构件弦长残差为零，只要跨列出现分支跳变也不得标记 `status=success`。

对 `r=p\theta/(2\pi)` 的向内盘入刚性链，龙头参数随时间减小，但位于其后的串联节点在外侧，因此链上空间顺序必须满足 `\theta_{i+1}>\theta_i`。求根只能在当前参数右侧括取最近物理解；在 `[0,\theta_i]` 搜索、把无根节点置零或让尾部坍缩到原点均判失败。结果合同须保存 `max_distance_residual_m`、`initial_head_radius_m` 和 `initial_tail_radius_m`，要求最大弦长残差不超过 `10^{-6}` m 且初态尾部极径大于头部极径。官方模板中所有带行列表头的数值交叉格必须完整回填，不能跳过中间连接点或龙尾前把手。

刚性链速度的主值必须由连接弦约束对时间微分后，结合相邻节点路径切向投影递推；规定的龙头速度须按构造逐时精确满足，不能在结果末尾只覆盖龙头一列。对位置做有限差分只可作为独立交叉核验，不能取代约束微分；两者不一致、出现不合理尖峰或需“选择更可信的一组”时，应判定根分支/时间延拓失败并停止。

分段路径接头必须分别计算位置残差、单位切向夹角和两侧曲率。不同半径的相切圆弧只能通过位置/切向 C1 检查，曲率会按 `1/R` 跳变；不得把相切残差为零写成 C2 或曲率连续。

串联几何程序须从拓扑表生成约束数组并断言数组长度等于构件数；首段异质时，其余统一长度重复 `n-1` 次。对 `r=p\theta/(2\pi)`，若输入位置是第 `N` 圈，则初始化 `\theta=2\pi N`、`r=Np`，并在正式求解前以独立断言复算，禁止对圈数重复除以 `2\pi`。

碰撞轮廓数组必须由构件真实总长、总宽和连接点外伸量生成，运动学孔距只能生成节点距离约束数组。二者分别保存并检查单位，禁止以孔距替代有向矩形全长；1 基节点表须断言末端编号等于构件数加一。

若候选路径参数的可行性要求系统到达指定边界，程序必须沿完整运动区间复用有限长宽实体碰撞/干涉核，并把首次失效时刻与边界到达时刻比较。初态即边界的零步结果或只检查轨迹方程有交点，不得标记为可行最小值。

内生决策响应模型须保存 `decision_response_audit`，至少含 `decision_variable`、`response_variable`、`assignment_mechanism`、`confounders`、`identification_design`、`identification_assumptions`、`response_semantics`、`decision_bounds`、`boundary_hit_rate`、`response_scenarios` 和 `robust_replay`。若 `identification_design=observational_only`，输出只能标记为关联预测或情景优化，不得标记因果最优。至少运行一组响应系数扰动和一组时间/实体外回测；最优决策大量贴边而未扩大/解释安全域，或仅在训练内报告拟合优度时，不得标记 `status=success`。

边界候选须保存向可行域内部的扰动表。若近似目标形成等价脊/参数带，输出带的范围和可辨识性说明；若约束外候选看似更优，必须保留为负面测试并断言闸门拒绝。优化器返回值经过静默裁剪、四舍五入到边界或只在代理目标上更优时，`optimality_claim` 不得超过 `feasible_only`。

逆问题、定位、反演、编队和标定结果须在每个相关 JSON 保存 `identifiability_audit`，至少包含 `unknown_dimension`、`independent_observation_dimension`、`gauge_transformations`、`anchors_or_priors`、`jacobian_rank`、`smallest_singular_value`、`condition_number`、`discrete_ambiguity_count` 和 `invariance_negative_tests`。代码必须验证锚定后的雅可比达到声明秩，并实际运行至少一个平移/旋转/尺度/镜像/标签置换负例；若负例仍满足观测且未由锚点或先验排除，结论只能是等价类或多解。不得以残差近零、方程数较多或求解器 `success` 代替可辨识性证据。

声称多轮迭代调整或控制收敛时，须保存 `iteration_history`，逐轮记录选择集合、目标/残差、最大状态更新、约束裕度和终止原因；至少运行两个不同初值或扰动规模。生成一张真实迭代曲线或逐轮表，并将其列入 `artifacts`。只保存初态与终态时不得写“经多轮收敛”，只能写“联合批处理回放可行”。

执行任何 EDA 前，先在 `data_manifest` 中冻结每个附件的角色：题面/说明、观测输入、待回填输出模板或静态资源。`result*.xlsx`、`output*.xlsx`、`submission*.xlsx` 和文件名含“结果模板”的表格默认为输出模板候选；其空白写入格不是缺失观测，不得计算缺失率、异常值、相关性或分布。最多用两次结构检查确认角色；确认是空白模板后立即转向题面常量、几何/量纲关系和可行域审计。只有包含非空观测样本且字段语义明确的文件才能进入数据驱动 EDA；无法确定时返回 `blocked_input_role`。

EDA 到写出来源/附件/参数/量纲审计合同即结束，不在该阶段求解后续子问、扫描候选参数、做全时域仿真或生成论文结果。若 EDA 合同的来源事实未过门禁，只允许按诊断定向修复一次；诊断已给出确定来源事实时，下一次工具调用必须直接修改并重写证据 JSON，不得再次读取、渲染或裁剪题图。修复仍失败就阻断，不得转去执行其他子问来规避错误。

代码阶段须从题目原文独立重建 `source_parameter_audit`，不得把建模报告当事实源。每个派生参数保存来源值、公式、统一单位、子问题作用域和范围断言；内部长度、概率、质量、面积与计数须分别满足其自然边界。以构件内部点距为例，若总长为 $L$、两端偏移为 $e_1,e_2$，必须断言 $d=L-e_1-e_2$ 且 $0<d\le L$；加号公式或超出整体尺寸的值作为负例拒绝。题面事实与候选方案冲突时先纠正候选方案；无法唯一修复时输出 `blocked_source_facts`，禁止生成正式结果或论文。

题面引用图示且关键方向、坐标、端点或连接关系依赖该图时，读取本地官方 PDF/图片，并在 EDA 证据合同的 `data_scope.source_figures` 数组逐图记录 `file`、从 1 开始的 `page`、`figure` 和具体 `facts`；PDF 所报页必须实际含“图 N + 图名”的图注，正文里的“见图 N”引用不算图所在页。命名点必须记录它与坐标轴、内外端或方向的明确相对关系。只写“已查看/已核验”，或写“未给出、仅示意、需约定”，均不算提取事实。文件不存在、页码/图号缺失或无法可靠辨认即阻断，不得声称“没有图”后按惯例猜测。

同一关键题图最多使用两次工具调用检查：一次逐页定位完整图注，一次渲染或独立核验。不得根据正文顺序、截断输出或 `problem.txt` 的换页布局猜测 PDF 页码；须在每个 PDF 页的独立提取文本中查找行首“图 N + 图名”。取得官方文件、页码、图号和具体事实后立即进入求解并写结果合同，禁止对同一页面的派生裁剪反复做像素分析。

坐标实现须分别核对路径参数增减、极径增减和标准平面方位角。题图若把起点放在正 x 轴且题面要求顺时针运动，起点后的小时间步必须进入下半平面；递增路径参数不能未经符号映射直接代入 `x=r\cos\theta, y=r\sin\theta`。将该局部象限或坐标符号作为来源方向的独立验算。

每个代码子任务必须保存 `results_<subtask>.json`，固定包含 `status`、`subtask`、`data_scope`、`assumptions`、`model`、`numeric_results`、`validation` 和 `conclusion_bounds`。`numeric_results` 至少有一个有限可复算数值，`validation.passed=true` 且 `checks` 非空；缺合同、只有文字结论或验证未通过时不得进入写作。题面指定 Excel 模板时还须原位新增数值，并证明工作表、固定文字、公式、合并区域和样式未变化。

跨子问题参数隔离须贯穿所有结果合同字段。不能在建模方案中声明完整候选域，却在 EDA 或后续 `conclusion_bounds` 中把前问的初态、螺距或阈值重新写成后问搜索下界；优化边界必须保存本问原文来源，或保存由完整实体可行性核独立证明被裁区间不可行的证据。

题目提供 Excel/CSV 结果模板时，最终产物必须由保留模板结构和样式的表格引擎写入。写后重新导入，对每个可写区域逐格比对结构化结果；同时检查工作表名、固定说明、公式、合并区域和非填写单元未变化。范围收缩、错列、四舍五入差异或模板公式被覆盖均为失败，不能只凭“文件能打开”放行。

模板写回必须使用显式十进制舍入（例如 `Decimal.quantize(..., ROUND_HALF_UP)`），并在 `submission_export` 中记录小数位数、tie-breaking、边界输入/期望/实际值以及导出政策。不得依赖语言默认 `round`；至少测试一个恰好为半单位的值。若当前最优性声明低于正式导出要求，只能生成带 `DRAFT_FEASIBLE_ONLY` 标识的审计草稿，禁止输出看似正式的提交文件名。

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

代码阶段结束前，按 `results/results_contract_manifest.json` 逐个检查正式子问题契约。任何清单项缺少结果文件、数据哈希、样本量、验证记录或图表路径，或清单与题目顶层问题不一致时，必须阻断写作阶段，并在 `reports/RESULTS_REPORT.md` 中给出可操作的修复项。辅助 JSON 只按其自身审计用途检查，不得冒充子问题契约，也不得因目录全量扫描而产生假失败。题面有资源目标时，缺少可运行基线、资源单位、最坏情景资源汇总或严格改善证据同样必须阻断写作阶段。写作手只能读取通过闸门的结构化结果，不能从自然语言错误日志猜测数值。

写作前还必须生成并实际执行 `reproduction_manifest.json`。清单只允许复制官方输入、代码、静态模板和必要字体/样式；不得把已有 `results/`、`figures/`、`paper/`、`generated/`、缓存或报告列为重放输入。每条命令使用相对工作目录且按序执行，前一命令生成的派生文件才可被后一命令读取。清单的 `expected_outputs` 至少覆盖正式契约清单中的全部 JSON 和所有数据图；若脚本写入约定外目录或依赖旧绝对路径，标记 `reproduction_failed` 并阻断写作。
