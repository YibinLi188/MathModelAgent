# MathModelAgent 升级说明

本 fork 基于 `jihe520/MathModelAgent@11f38624cd9128bc2ce22d7b3254106e624490cd`，保留上游来源和 `docs/md/License.md`。本次改动针对同题基线论文与两套数学建模资料中反复出现的可复现性、样本边界和验收问题。

## 已实现

- 为 Agent 间结果增加 Pydantic 结构化状态：成功/失败、执行次数、代码输出、产物和错误信息。
- 增加 `quality_gates.py`，在 Modeler、Coder、Writer 交接处阻断缺字段、失败结果、越界/不存在产物和占位符。
- Coder 每个子任务重置聊天轮次；未实际调用 `execute_code` 或超过预算时返回失败状态，不能把错误文本传给 Writer。
- Modeler JSON 解析取消基于正则猜字段的兜底，改为严格 JSON/对象解析并交给 Pydantic 校验。
- Writer 图片规则按 Markdown/LaTeX 分流；引用规则允许同一文献在正文多处规范引用但只登记一个参考文献条目。
- 修复最终拼接时重复引用被错误重新编号的问题。
- 在 1start、2analysis、3coding、5writing、6verity 中加入数据清单、哈希、时间切分、独立重算和失败阻断要求。

## 验证状态

- `python -m compileall -q backend/app`：通过。
- `backend/app/tests/test_quality_gates.py`：已添加；当前机器未安装 `pytest` 和后端依赖（包括 `pydantic`），因此未执行运行时测试。
- 真实四 Agent API 回归：未执行，当前没有 Coordinator/Modeler/Coder/Writer 的模型 API 配置。

## 许可边界

请继续遵守上游 `docs/md/License.md`：个人免费使用；禁止商业用途、闭源分发和基于项目提供商业服务。该 fork 不改变上游许可含义。
