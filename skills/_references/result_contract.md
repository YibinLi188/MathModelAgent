# 数学建模结果契约

代码阶段和验收阶段共享以下最小证据链：

```text
题面/附件 -> data_manifest.json -> 模型参数与代码 -> results/quesN.json
           -> figures/* + RESULTS_REPORT.md -> 论文正文 -> VERIFY_REPORT.md
```

每个 `results/quesN.json` 至少包含：

| 字段 | 要求 |
| --- | --- |
| `schema_version` | 当前为 `1.1` |
| `status` | 只表示计算流程是否完整执行：成功为 `success`；执行失败为 `failed` 并填写 `error`。不得用它代替求解器收敛或最优性声明 |
| `task` | 稳定的问题标识，如 `ques1` |
| `data_hashes` | 输入数据或参数快照的 SHA-256，不能为空 |
| `sample` | 样本量、仿真步数或重复次数，不能用自然语言代替 |
| `metrics` | 数值指标及其单位对应的结构化结果 |
| `metric_semantics` | 说明指标是事件概率、成功对象数、节点/系统指标，及分子、分母、单位、并发计数规则 |
| `parameters` | 本次运行的完整参数，而非只写默认值 |
| `artifacts` | 结果表、图表、日志的相对路径，且文件必须存在 |
| `validation` | `independent_recompute=true`、`independent_delta` 和 `tolerance`，以及约束检查结果 |
| `solution_evidence` | 区分可行性、求解器收敛和最优性；字段要求见下文 |
| `optimization_domain` | 优化任务必填：决策变量、类型、上下界、开闭边界、组合来源、插值/外推、安全域与验证切分 |
| `limitations` | 近似、未覆盖情景和外推边界 |
| `error` | 成功时为 `null` |

`solution_evidence` 的最小结构为：

```json
{
  "feasibility_status": "feasible | infeasible | not_applicable",
  "solver_converged": false,
  "termination_reason": "maximum function evaluations reached",
  "optimality_claim": "global_proven | local_converged | feasible_only | not_applicable",
  "restart_or_budget_checks": 3,
  "stability_evidence": "three budgets produced the same feasible objective within 0.2%"
}
```

`status=success` 只说明计算和产物生成成功。若 `solver_converged=false`，`optimality_claim` 只能为 `feasible_only` 或 `not_applicable`；正文必须写“可行近似解/方案”，不得写“最优解”或暗示全局最优。若声明 `local_converged` 或 `global_proven`，必须同时有 `solver_converged=true`；`global_proven` 还需在 `stability_evidence` 中写明证明、界或穷举依据。

当指标存在合理但不唯一的物理/统计口径，或同题高质量参考结果明显冲突时，结果 JSON 还必须包含 `comparison_semantics`：

```json
{
  "comparison_semantics": {
    "surface_or_entity_model": "planar triangular panel",
    "numerator": "projected incident area whose reflected ray hits the receiver disk",
    "denominator": "projected area inside the 300 m aperture",
    "weighting": "projected area",
    "sampling_unit": "uniform point within each triangle",
    "boundary_rule": "triangle samples outside aperture are excluded",
    "uncertainty": "10000 samples per triangle; 100 repeated runs",
    "comparable_reference_ids": ["A217"]
  }
}
```

比较前必须对齐表面/对象模型、分子、分母、权重、采样单位、边界和不确定性。定义不同的裸数值不得直接排序或写成精度差距；应分别报告为口径敏感性。

优化任务的最小 `optimization_domain` 结构为：

```json
{
  "decision_variables": [
    {"name": "temperature_c", "type": "continuous", "lower": 250, "upper": 350, "lower_exclusive": false, "upper_exclusive": true}
  ],
  "combination_scope": "observed_combinations_only",
  "interpolation": "piecewise_linear_within_each_observed_range",
  "extrapolation": "forbidden",
  "safety_constraints": ["temperature_c <= 450"],
  "validation_split": {"group_key": "catalyst_combination", "overlap_count": 0},
  "reported_points": [
    {"label": "engineering point", "role": "feasible_candidate", "values": {"temperature_c": 349}},
    {"label": "left-limit reference", "role": "supremum_reference", "values": {"temperature_c": 350}}
  ],
  "grid_step": 0.1,
  "boundary_interpretation": "open upper bound; report supremum and a separate engineering-margin point"
}
```

`combination_scope` 必须区分 `observed_combinations_only`、`interpolated_design_space` 与 `extrapolated_candidate_space`。`reported_points.role` 只能为 `feasible_candidate`、`supremum_reference` 或 `infeasible_reference`；验证器会逐变量检查所有可行候选是否真正满足开闭边界。严格不等式使用 `*_exclusive=true`；若可行域开边界导致不存在最大值，`solution_evidence.optimality_claim` 不得写 `global_proven`，核心指标应分别给上确界近似与工程裕度点。

题面含计算、存储、时间、成本、能耗或资源利用率目标时，还必须包含 `resource` 对象。该对象是结果声明，不替代独立复算：

```json
{
  "resource": {
    "status": "resource_passed",
    "decision_rule": "strict_improvement | pareto_tradeoff",
    "quality_constraints": {"rho_min_ge_0_99": true},
    "baseline": {"id": "...", "run_command": "...", "metrics": {"runtime": {"value": 1.0, "unit": "s", "direction": "min"}}},
    "candidate": {"id": "...", "run_command": "...", "metrics": {"runtime": {"value": 0.8, "unit": "s", "direction": "min"}}},
    "comparison": {
      "strict_improvements": ["runtime"],
      "accepted_tradeoffs": [],
      "worst_case_scope": "..."
    }
  }
}
```

`baseline` 与 `candidate` 的每项用于比较的资源指标必须具有相同的名称、单位和方向；`strict_improvements` 中每项必须按其方向严格优于基线。`quality_constraints` 中不得有 `false` 值。对于天然存在存储--编码成本冲突的压缩题，可使用 `pareto_tradeoff`：至少一项题设资源必须严格改善，未改善项必须逐项列入 `accepted_tradeoffs`，写明方向、数值、原因和结论边界。此时论文只能陈述已验证的帕累托取舍，不能概括为“所有资源均降低”。

统计对象的语义必须保持一致：

- `event_probability`：一个事件在时间窗中发生的概率，例如“至少一个节点发送”。
- `successful_object_count`：该时间窗内成功对象的数量，例如成功数据包数；并发成功对象必须逐个计数。
- `throughput`：成功对象数量乘有效载荷，再除以实际时间；必须声明 bit/byte 和秒/us 的换算。

独立复核必须使用不同的纯函数、保存的中间表或边界枚举；不得只是再次读取论文数字或调用完全相同的生成函数。
