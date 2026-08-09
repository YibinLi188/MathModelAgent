# 数学建模结果契约

代码阶段和验收阶段共享以下最小证据链：

```text
题面/附件 -> data_manifest.json -> 模型参数与代码 -> results/quesN.json
           -> figures/* + RESULTS_REPORT.md -> 论文正文 -> VERIFY_REPORT.md
```

每个 `results/quesN.json` 至少包含：

| 字段 | 要求 |
| --- | --- |
| `schema_version` | 当前为 `1.0` |
| `status` | 成功必须为 `success`；失败必须为 `failed` 并填写 `error` |
| `task` | 稳定的问题标识，如 `ques1` |
| `data_hashes` | 输入数据或参数快照的 SHA-256，不能为空 |
| `sample` | 样本量、仿真步数或重复次数，不能用自然语言代替 |
| `metrics` | 数值指标及其单位对应的结构化结果 |
| `metric_semantics` | 说明指标是事件概率、成功对象数、节点/系统指标，及分子、分母、单位、并发计数规则 |
| `parameters` | 本次运行的完整参数，而非只写默认值 |
| `artifacts` | 结果表、图表、日志的相对路径，且文件必须存在 |
| `validation` | `independent_recompute=true`、`independent_delta` 和 `tolerance`，以及约束检查结果 |
| `limitations` | 近似、未覆盖情景和外推边界 |
| `error` | 成功时为 `null` |

统计对象的语义必须保持一致：

- `event_probability`：一个事件在时间窗中发生的概率，例如“至少一个节点发送”。
- `successful_object_count`：该时间窗内成功对象的数量，例如成功数据包数；并发成功对象必须逐个计数。
- `throughput`：成功对象数量乘有效载荷，再除以实际时间；必须声明 bit/byte 和秒/us 的换算。

独立复核必须使用不同的纯函数、保存的中间表或边界枚举；不得只是再次读取论文数字或调用完全相同的生成函数。
