---
name: 6verity
description: "数学建模竞赛最终验证和验收阶段，支持 Typst 和 LaTeX 双引擎。用于论文写完后检查章节数量、标题顺序、图表引用、数值一致性、占位符、内部文件泄露、参考文献、代码可复现性、编译和提交就绪状态。"
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob, Agent, WebSearch, WebFetch
---

# 验证和验收（Typst / LaTeX）

本 skill 是完整工作流的最后一关。它不重新建模、不生成新结果、不代替写作阶段重写论文；它负责发现硬错误、修复可直接修复的问题，并输出 `reports/VERIFY_REPORT.md`。

## 数学建模规范参考

如需领域判断，读取 `../_references/math_modeling_norms.md` 中的"论文验收与一致性"小节。该文件只是规范知识库，不是固定执行流程；具体目录、入口文件、结果文件和图表目录由当前项目结构决定。
结构化结果字段和指标语义按 `../_references/result_contract.md` 执行。

## 阶段边界

- 本阶段负责：结构验收、文本质量门禁、图表引用检查、结果一致性检查、Typst/LaTeX 编译检查、PDF 视觉检查、提交清单。
- 本阶段不负责：重新设计模型、重新跑大规模实验、重新组织整篇论文。
- 发现硬错误时，优先做小范围修复；如果需要回到前序阶段，写入 `reports/VERIFY_REPORT.md` 并标记为未通过。

## 输入

由模型先根据当前工作区判断项目布局，再把实际路径传给检查脚本。常见输入包括但不限于：

1. 论文入口文件：`main.typ`（Typst）或 `main.tex`（LaTeX）。
2. 正文章节目录或若干正文文件（`.typ` 或 `.tex`）。
3. 参考文献文件（`references.typ` 或 `references.tex`）。
4. 前序阶段的分析、建模、结果、图示报告。
5. 图表目录
6. 可复现代码目录。
7. 编译后的 PDF，或可由入口文件编译得到的输出 PDF。

不要假设论文目录一定叫 `paper/`，也不要假设结果文件一定在项目根。若项目使用不同命名，按实际结构传参并在 `reports/VERIFY_REPORT.md` 中说明。

## 工作流程

### Step 0：结构化结果闸门（先于文本检查）

先扫描 `results/*.json` 和 `data/data_manifest.json`。每个顶层子问题都必须有可解析 JSON、`schema_version=1.1`、`status=success`、数据哈希、样本量、核心指标、产物路径、验证记录和 `solution_evidence`。若任一文件缺失、状态为 `failed`、哈希为空或产物不存在，直接判定 `FAIL`，不得用论文中的自然语言补齐。

若本 Skill 附带 `scripts/validate_results_contract.py`，先运行：

```bash
python <skill-dir>/scripts/validate_results_contract.py \
  --results-dir <project-root>/results \
  --project-root <project-root> \
  --expected-tasks ques1,ques2,ques3
```

Windows PowerShell 使用 `python`；如果系统只有 `python3`，替换为 `python3`。按题目实际问题数替换 `--expected-tasks`。该脚本是结构检查，不替代模型 oracle；脚本失败必须保留失败输出并阻断写作。

对至少一个核心指标执行独立重算：优先调用项目提供的验证脚本；没有独立脚本时，使用保存的中间表和第二段纯函数计算。记录两次结果及绝对差，超过项目声明容差即 `FAIL`。时间序列必须检查训练集年份严格早于验证/回放年份，并确认标准化、填补和编码未使用未来数据。

结果契约还必须声明指标语义：事件概率、成功对象数、节点级指标和系统级指标不可混用。检查吞吐、流量、计数等指标的单位、分子、分母和并发规则；“至少一个对象发生”不能直接作为“成功对象数”。每个核心指标必须有 `metric_semantics`、`independent_delta` 和 `tolerance`，缺失即 `FAIL`。

分别检查可行性、收敛和最优性：`solver_converged=false` 时只允许 `optimality_claim=feasible_only|not_applicable`，并核对摘要、正文和结论没有使用“最优解/全局最优”等越级措辞。`local_converged` 或 `global_proven` 必须有正常终止原因和稳定性证据；`global_proven` 还必须有界、穷举或证明。状态与措辞冲突即 `FAIL`。

若同题参考结果冲突或模型存在多种物理/统计口径，检查 `comparison_semantics` 及口径敏感性结果。表面/对象模型、分子、分母、权重、采样单位或边界不同的数值被直接计算相对误差、排序或当作正确性证据时，判定 `FAIL`。

对所有优化结论检查 `optimization_domain`：变量类型、上下界、开闭边界、是否允许未观测组合、插值/外推和安全域任一缺失则 `FAIL`。题面严格不等式被实现为闭边界、网格最靠近边界点被宣称为精确最优、代理模型外推值与实测/插值值未分层标注，均判定 `FAIL`。若一组实体有多条观测，验证划分必须报告分组键与组间重叠计数；用行级随机拆分宣称新实体泛化时判定 `FAIL`。

题面将 0 定义为未观测、未交易、未运输或不适用时，检查结构零掩码、有效样本数与反例测试。结构零被纳入损耗率/成功率/均值/分位数，或正文未声明处理规则，判定 `FAIL`。

跨期规划必须从决策变量独立重放 `state_trace`。任一期状态转移不守恒、库存/容量/安全下界违反、只满足总量却存在前缀缺口，均判定 `FAIL`。对“最少数量”或“最大产能”核对其预测分位数、损耗压力、初始库存和求解域；未与情景绑定的单一整数/百分比最多为 `WARN`，若摘要称为无条件结论则 `FAIL`。

存在官方结果模板时，检查重新导入后的逐格比对报告。工作表名、固定单元、公式、合并区域或非填写区发生变化，写入范围错列/缩减，或结构化结果与单元格有任一超容差差异，均判定 `FAIL`；“成功导出/可打开”不能代替模板验收。

题目要求新增少量实验时，逐项检查其信息目标与判废准则。全部实验只是无理由均匀铺点、重复已有点却未说明用于纯误差/复验、或候选越出题面与安全可行域时，判定 `FAIL`；若没有任何峰值、边界、交互、模型判别或重复误差证据目标，最多只能 `WARN`，不得写成“最优实验设计”。

检查 `reports/QUESTION_COVERAGE.md`（若入口阶段生成）中的每个顶层问题和 `gap` 状态。存在未覆盖的题面边界、拓扑情景或参数范围时，验收结论最多为 `WARN`；若论文摘要声称已完成全部问题，则判定 `FAIL`。

若题面含计算、存储、时间、成本、能耗或资源优化目标，检查 `reports/RESOURCE_BASELINE.md` 和结果 JSON：每个优化子问题必须存在可运行基线、统一资源单位、质量约束、候选表、最坏情景资源聚合和严格改善的可复算证据。`resource.comparison.strict_improvements` 至少包含一项同单位严格改善；`pareto_tradeoff` 还必须逐项列出未改善的资源、数值、原因和结论边界。候选仅精度通过、资源只在均值上变好、资源计数遗漏模型/编解码/推理等题面要求部分，或把帕累托取舍写成全维度优化时，判定 `FAIL`；论文不得把该子问题写成完成。没有资源目标的题目跳过本项，并在报告中说明。

若 `paper/` 只有 `paper.md` 而没有选定引擎的 `main.typ`/`main.tex` 和编译 PDF，必须标记为“草稿未提交就绪”，不能写 `PASS`。


### Step 1: 运行文本质量门禁

优先运行本 skill 的脚本。脚本按入口文件扩展名自动选择检查逻辑（`.typ` → Typst 检查，`.tex` → LaTeX 检查）：

```bash
set -o pipefail
mkdir -p _tmp
SCRIPT_PATH="<按当前 skill 实际位置确定>/scripts/writing_check.sh"
bash "$SCRIPT_PATH" \
  --paper-dir "$PAPER_DIR" \
  --main "$MAIN_FILE" \
  --sections-dir "$SECTIONS_DIR" \
  --references "$REFERENCES_FILE" \
  --figures-dir "$FIGURES_DIR" \
  --results-file "$RESULTS_FILE" \
  --problem-analysis "$PROBLEM_ANALYSIS_FILE" \
  --all-results "$ALL_RESULTS_FILE" \
  | tee _tmp/writing_check.log
```

如果本 skill 被复制到其他目录，使用实际脚本路径。可以先运行 `bash <script> --help` 查看参数。不要把脚本路径、论文目录或文件名写死在验收逻辑中。

脚本只扫描文本，不生成论文，也不编译 PDF。它的 `FAIL` 属于硬错误，必须修复后重跑。

### Step 2: 章节数量和标题顺序

**Typst 引擎**检查：

- 入口 `.typ` 文件中 `#include("...")` 的数量是否与实际正文结构匹配。
- include 顺序是否符合文件名前缀顺序，例如 `1_...`, `2_...`, `3_...`。
- 每个 section 是否有明确一级标题（`= 标题`，等号后有空格）。
- 标题顺序是否符合所选论文类型。

**LaTeX 引擎**检查：

- 入口 `.tex` 文件中 `\input{...}` 或 `\include{...}` 的数量是否与实际正文结构匹配。
- 章节顺序是否符合文件名前缀顺序。
- 每个 section 是否有 `\section{}` 或对应级别标题。

通用检查（两种引擎）：

- 章节文件是否缺失、重复引用、未被引用。
- 如果题目不是三问，不强行要求三段问题章节；按 `ANALYSIS_MODELING_REPORT.md` 的子问题数量核对。

### Step 3: 图表和章节匹配

**Typst 引擎**检查：

- 图表目录中的 PDF 是否在正文中被引用。
- `#figure(image(...), caption: [...])` 的图片是否真实存在。图片路径必须相对于 `.typ` 文件。
- 数据图是否放在对应结果/分析章节，非数据流程图是否放在方法/总体思路章节。

**LaTeX 引擎**检查：

- `\includegraphics{}` 引用的图片文件是否真实存在。路径相对于 `.tex` 文件。
- `\caption{}` 是否存在。
- 数据图是否放在对应结果/分析章节。

通用检查（两种引擎）：

- 连续图表之间是否有足够解释文字。
- caption 是否过长、过泛或与图意不一致。
- 图表编号、正文引用和章节语义是否一致。
- 正文必须有实际图片嵌入语法；仅出现反引号文件路径、自然语言路径或未解析的 Markdown 路径不算图表引用。

不要生成 `*_typst_includes.typ` 或 `*_latex_includes.tex`；图表必须直接嵌在对应 section 中。

### Step 4: 写作质量和泄露检查

检查并修复：

- `TODO`、`PLACEHOLDER`、`待补充`、`待续写`、`示例数据` 等占位符。
- 论文正文出现内部工作流文件名、临时目录名、代码目录名或结果 JSON 路径。
- 过多列表式写作（Typst 中大量 `#list`、`enum`，LaTeX 中大量 `\begin{itemize}`、`\begin{enumerate}`）。
- 段落反复以"如图""由图""图 X 展示了"开头。
- 图表后没有解释、公式后没有变量含义、结论只报数不解释。

### Step 5: 数值和结果一致性

检查：

- 论文中的关键数值必须来自当前工作流声明的结果记录或结果 JSON。
- 目标函数值、误差指标、排名、权重、阈值、灵敏度结果不得与结果记录冲突。
- 如果存在汇总结果 JSON，抽取关键指标并确认论文正文中有对应结果。
- 公式中的符号应在符号说明或正文首次出现处解释。

发现数值冲突时，不要自行发明新结果；应回到结果记录或代码输出修正论文。

同时核对结果 JSON 的指标语义和论文公式：若理论分子统计的是事件而论文结论声称统计成功对象，必须退回代码阶段修正；不能通过重新计算一个相同错误的公式来“自证”。

同时检查数据血缘：论文关键数字必须能在 `results/*.json` 找到，结果 JSON 的 `data_hashes` 必须能在 `data/data_manifest.json` 找到，快照文件必须仍存在。代理变量、事后回放和缺少官方口径等限制必须同时出现在论文和验收报告中。

### Step 6: 引用和模板规范

检查：

- 参考文献文件是否存在，或模板是否采用了其他真实参考文献机制。
- 正文引用标记（Typst 的 `@label`/`#super`，LaTeX 的 `\cite{}`）是否能对应到真实参考文献。
- 中文论文 caption、表题、摘要语言保持中文；英文论文保持英文。
- 选定的模板入口是否保留所选比赛模板的必要封面、摘要、编号、页眉页脚或提交格式。
- 不要把模板结构误删成普通空白文档。


### Step 7: 编译

**Typst 编译**：

```bash
command -v typst >/dev/null 2>&1 && typst compile "$MAIN_FILE" "$OUTPUT_PDF"
```

**LaTeX 编译**：

```bash
command -v xelatex >/dev/null 2>&1 && xelatex -interaction=nonstopmode "$MAIN_FILE" && xelatex -interaction=nonstopmode "$MAIN_FILE"
```

xelatex 需跑两遍解决目录和交叉引用。

编译失败必须修复语法、路径、图片引用或模板问题后重跑。编译通过后确认输出 PDF 非空。

### Step 8: PDF 视觉检查

如果模型有视觉能力，必须把编译后的 PDF 每页导出为 PNG 并逐页查看。这个步骤用于发现纯文本扫描和编译器无法发现的版式错误。若 PDF 来自回退渲染器而非用户选定入口的成功编译，仍可做视觉检查，但只能报告 `rendered_preview`，不能取代编译 PASS。

优先使用系统已有工具导出页面 PNG；不要为了视觉检查引入沉重依赖。可选命令示例：

```bash
mkdir -p _tmp/pdf-pages
if command -v pdftoppm >/dev/null 2>&1; then
  pdftoppm -png -r 160 "$OUTPUT_PDF" _tmp/pdf-pages/page
elif command -v mutool >/dev/null 2>&1; then
  mutool draw -r 160 -o _tmp/pdf-pages/page-%03d.png "$OUTPUT_PDF"
elif command -v magick >/dev/null 2>&1; then
  magick -density 160 "$OUTPUT_PDF" _tmp/pdf-pages/page-%03d.png
else
  echo "No PDF rasterizer found; record visual check as not run."
fi
```

导出后逐页检查：

- 页面是否空白、缺页、页数异常或页面尺寸异常。
- 标题、摘要、正文、页眉页脚、页码是否被裁切或位置明显错误。
- 表格是否超出页边距，单元格文字是否重叠、溢出、被截断。
- 图片、图题、表题、公式、编号是否与正文重叠。
- 公式是否越界，长公式是否压到页边距或下一段文字。
- 列表、段落、脚注、参考文献是否出现异常大空白、重叠或孤立残行。
- 中文/英文/数学符号字体是否明显缺字、乱码或 fallback 异常。
- 封面、摘要页、目录、附录等模板关键页面是否保留比赛要求的视觉结构。

如果是模板转换或已有参考 PDF 的项目，还应将不同引擎的 PDF 都逐页导出 PNG，按页对比版式差异；页数或页面尺寸不一致必须记录为硬错误或明确说明原因。

如果模型没有视觉能力，必须在 `reports/VERIFY_REPORT.md` 中明确写出“未执行视觉检查”的原因，并至少完成 PDF 非空、页数、页面尺寸等可程序化检查。

### Step 9: 写验收报告

创建 `reports/VERIFY_REPORT.md`：

```markdown
# 验证和验收报告

## 结论
PASS / FAIL

## 检查项
| 检查项 | 结果 | 说明 |
| --- | --- | --- |

## 章节结构

## 图表引用

## 数值一致性

## 文本质量门禁

## 编译

## PDF 视觉检查

## 仍需处理的问题
```

验收报告必须列出实际运行根目录、入口文件、结果 JSON、图表、代码版本、依赖版本、随机种子、运行命令、独立复算公式及 SHA-256。目录存在性检查只能作为辅助项，不能替代数学正确性和跨文件一致性检查。

只有当硬错误都修复、文本门禁通过、核心图表都引用、数值一致、编译通过或明确说明不可编译原因、视觉检查通过或明确说明无法执行原因时，才写 `PASS`。

## 硬错误标准

以下问题必须判定 `FAIL`：

- 缺少选定的论文入口文件（`main.typ` 或 `main.tex`）或核心正文。
- 论文入口引用的章节文件不存在。
- Typst 入口缺少 `#include`；LaTeX 入口缺少 `\input`/`\include`。
- 正文章节缺少一级标题（Typst `= ` 后缺空格，LaTeX `\section{}` 缺失）。
- 章节顺序明显错误或重复。
- 正文仍有占位符。
- 正文泄露内部工作流文件名。
- 引用的图片不存在。
- 关键数值与结果记录冲突。
- 编译器可用但论文编译失败。
- 编译后的 PDF 为空、缺页、页数异常或页面尺寸异常且无法解释。
- 视觉检查发现正文、表格、图片、公式、页眉页脚、页码等关键元素重叠、裁切、越界或乱码。
- 缺少结构化结果/数据清单，或独立重算失败。
- 题面有资源优化目标但缺少严格资源改善证据，或把 `resource_gap` 写成已完成。
- 所选排版引擎可用却编译失败、超时或依赖交互安装，而将其他渲染器的 PDF 标为提交就绪。
- 代码失败结果被写入论文，或论文数值无法追溯到结果 JSON 和数据哈希。

## 警告标准

以下问题可判定为 `WARN`，但应尽量修复：

- 未引用的备用图片。
- 某章节过短或明显不均衡。
- caption 偏长。
- 参考文献偏少。
- 图表后解释文字不足。
- 视觉检查工具不可用，但已经记录原因并完成基础 PDF 元数据检查。
- 代码完整复现耗时过长，只做了轻量检查。
