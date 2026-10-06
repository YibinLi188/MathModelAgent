"""代码手 Agent 模块，负责生成和执行 Python 代码完成建模任务。"""

import asyncio
from pathlib import Path

from app.core.agents.agent import Agent
from app.config.setting import settings, ApiType
from app.utils.log_util import logger
from app.services.redis_manager import redis_manager
from app.schemas.response import SystemMessage, InterpreterMessage
from app.tools.base_interpreter import BaseCodeInterpreter
from app.core.llm.llm import LLM
from app.schemas.A2A import CoderToWriter
from app.core.prompts import CODER_PROMPT
from app.utils.common_utils import get_current_files
import json
import math
import re
from app.core.prompts import get_reflection_prompt
from app.core.functions import coder_tools, coder_tools_anthropic
from app.core.quality_gates import (
    format_source_figure_requirements,
    QualityGateError,
    format_source_guardrails,
    load_evidence_contract,
    snapshot_spreadsheet_template,
    validate_spreadsheet_template_output,
)

# TODO: 时间等待过久，stop 进程
# TODO: 支持 cuda
# TODO: 引入创新方案：


def classify_input_file_role(file_name: str) -> str:
    """Return a deterministic first-pass role hint for an uploaded file."""
    normalized = file_name.replace("\\", "/").rsplit("/", 1)[-1].lower()
    suffix = normalized.rsplit(".", 1)[-1] if "." in normalized else ""
    if suffix in {"pdf", "doc", "docx", "txt", "md"}:
        return "problem_statement_or_instructions"
    if suffix in {"xlsx", "xls", "csv", "tsv"} and (
        re.match(r"^(?:result|output|submission)[-_ ]?\d*", normalized)
        or any(marker in normalized for marker in ("结果模板", "提交模板", "输出模板"))
    ):
        return "output_template_candidate"
    if suffix in {"xlsx", "xls", "csv", "tsv", "mat", "npy", "npz", "json"}:
        return "observational_data_candidate"
    return "static_resource_or_unknown"


def is_source_figure_inspection_code(code: str) -> bool:
    """Identify code that reads an official figure or rendered derivative."""
    reads_pdf_or_image = bool(
        re.search(
            r"(?:fitz\.open|PdfReader|pdfplumber\.open|get_pixmap|get_text\(|"
            r"Image\.open\([^\n)]*(?:fig(?:ure)?\d*|page\d*|crop))",
            code,
            re.IGNORECASE,
        )
    )
    reads_text_figure_layout = bool(
        re.search(r"problem\.txt", code, re.IGNORECASE)
        and re.search(
            r"(?:图\s*\d+|figure\s*\d+|图注|caption|题图|figure\s+layout)",
            code,
            re.IGNORECASE,
        )
    )
    return reads_pdf_or_image or reads_text_figure_layout


def has_unresolved_solver_failure(output: str) -> bool:
    """Detect solver failures that must not be converted to numeric fallbacks."""
    explicit_failure = bool(
        re.search(
            r"(?:warning|error|警告|错误).{0,160}(?:"
            r"无法.{0,80}(?:找到|求得).{0,40}(?:解|根)|"
            r"no\s+(?:valid\s+)?root|solver.{0,30}failed|"
            r"fallback|回退|退化值)",
            output,
            re.IGNORECASE | re.DOTALL,
        )
    )
    if explicit_failure:
        return True
    residual_pattern = re.compile(
        r"(?:max(?:imum)?\s*)?(?:(?:distance|constraint|link|rigid|"
        r"距离|约束|杆长|弦长)[^\n:=]{0,24})?"
        r"(?:residual|error|err|残差|误差)\s*[:=]\s*"
        r"([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[+-]?\d+)?)",
        re.IGNORECASE,
    )
    return any(
        math.isfinite(float(match.group(1))) and abs(float(match.group(1))) > 1e-6
        for match in residual_pattern.finditer(output)
    )


class CoderAgent(Agent):
    """代码手 Agent，通过 LLM 生成代码并在解释器中执行，支持错误反思和重试。"""

    def __init__(
        self,
        task_id: str,
        model: LLM,
        work_dir: str,  # 工作目录
        max_chat_turns: int
        | None = settings.MAX_CHAT_TURNS,  # 最大聊天次数，None表示无限制
        max_retries: int | None = settings.MAX_RETRIES,  # 最大反思次数，None表示无限制
        code_interpreter: BaseCodeInterpreter | None = None,
        context_window: int = 128000,
        cancel_event: asyncio.Event | None = None,
    ) -> None:
        super().__init__(task_id, model, context_window, cancel_event=cancel_event)
        self.work_dir = work_dir
        self.max_chat_turns = max_chat_turns
        self.current_chat_turns = 0
        self.max_retries = max_retries
        self.is_first_run = True
        self.system_prompt = CODER_PROMPT
        self.code_interpreter = code_interpreter

    async def run(
        self,
        prompt: str,
        subtask_title: str,
        source_text: str | None = None,
    ) -> CoderToWriter:  # type: ignore[reportIncompatibleMethodOverride]
        """执行代码手子任务，生成并运行代码。

        Args:
            prompt: 子任务描述。
            subtask_title: 子任务标题，用于分段输出。

        Returns:
            CoderToWriter 对象，包含代码执行结果和生成的图片列表。
        """
        logger.info(f"{self.__class__.__name__}:开始:执行子任务: {subtask_title}")
        assert self.code_interpreter is not None, "code_interpreter 未初始化"
        self.code_interpreter.add_section(subtask_title)
        # 每个子任务独立计数，避免前一个问题耗尽后续问题的预算。
        self.current_chat_turns = 0
        current_files = get_current_files(self.work_dir, "data")
        output_template_names = [
            file_name
            for file_name in current_files
            if classify_input_file_role(file_name) == "output_template_candidate"
        ]
        template_inspection_calls = 0
        source_figure_inspection_calls = 0
        source_inspection_images: set[str] = set()

        # 根据 api_type 选择 tools 格式
        api_type = self.model.api_type
        tools = coder_tools_anthropic if api_type == ApiType.ANTHROPIC else coder_tools

        # 如果是第一次运行，则添加系统提示
        if self.is_first_run:
            logger.info("首次运行，添加系统提示和数据集文件信息")
            self.is_first_run = False
            await self.append_chat_history(
                {"role": "system", "content": self.system_prompt}
            )
            # 当前数据集文件
            role_hints = {
                file_name: classify_input_file_role(file_name)
                for file_name in current_files
            }
            await self.append_chat_history(
                {
                    "role": "user",
                    "content": (
                        f"当前文件夹下的文件：{current_files}\n"
                        f"确定性附件角色提示：{role_hints}\n"
                        "角色提示为预筛选；输出模板候选只检查结构和写入区域，"
                        "不得把空白单元格当缺失观测反复分析。"
                    ),
                }
            )
            compact_template_summary = {}
            for file_name in output_template_names:
                path = Path(self.work_dir) / file_name
                if not path.is_file() or path.suffix.lower() not in {".xlsx", ".xlsm"}:
                    continue
                snapshot = snapshot_spreadsheet_template(path)
                compact_template_summary[file_name] = {
                    "sheet_names": snapshot["sheet_names"],
                    "sheets": {
                        name: {
                            "max_row": value["max_row"],
                            "max_column": value["max_column"],
                        }
                        for name, value in snapshot["sheets"].items()
                    },
                    "existing_numeric_cells": snapshot["numeric_count"],
                }
            if compact_template_summary:
                await self.append_chat_history(
                    {
                        "role": "user",
                        "content": (
                            "程序已读取的输出模板结构摘要："
                            f"{json.dumps(compact_template_summary, ensure_ascii=False)}。"
                            "不要为确认相同行列信息重复读取模板。"
                        ),
                    }
                )

        # 添加 sub_task
        logger.info(f"添加子任务提示: {prompt}")
        await self.append_chat_history({"role": "user", "content": prompt})
        evidence_file = f"results_{subtask_title}.json"
        required_templates = (
            sorted(
                set(
                    re.findall(
                        r"\b(?:result|output|submission)[-_ ]?\d*\.xlsx\b", prompt, re.I
                    )
                )
            )
            if re.fullmatch(r"ques\d+", subtask_title)
            else []
        )
        template_snapshots = {
            name: snapshot_spreadsheet_template(Path(self.work_dir) / name)
            for name in required_templates
            if (Path(self.work_dir) / name).is_file()
        }
        await self.append_chat_history(
            {
                "role": "user",
                "content": (
                    f"本子任务完成前必须通过 execute_code 写入 {evidence_file}，"
                    f"其中 subtask 必须精确写为 {subtask_title!r}；"
                    "顶层字段固定为 status='success'、subtask、data_scope、assumptions、"
                    "model、numeric_results、validation、conclusion_bounds；"
                    "numeric_results 至少包含一个可复算有限数值，validation 必须含 "
                    "passed=true 和非空 checks。写后重新读取并 print 完整合同。"
                    + (
                        f" 同时必须原位回填官方模板 {required_templates}，保留工作表、"
                        "固定文字、公式、合并区域和样式，并重新导入验证数值已写入。"
                        if required_templates
                        else ""
                    )
                    + (
                        " "
                        + format_source_guardrails(source_text)
                        + " 必须把其中 node_count 和全部 node_distance_m 原样写入 "
                        "numeric_results，程序将独立复核。"
                        if source_text
                        else ""
                    )
                    + (
                        " 本问采用 r=pθ/(2π) 且龙头顺时针向内盘入："
                        "龙头的θ随时间减小，但后续节点位于龙头后方外侧，"
                        "必须逐点满足θ_{i+1}>θ_i；只在θ_i右侧括取最近的物理根，"
                        "不得在[0,θ_i]搜索或把无根节点置零。"
                        "填表前断言0 s时所有相邻弦长残差<=1e-6 m、"
                        "龙尾极径>龙头极径，并回填模板每一个原始空白数值格，"
                        "包括龙尾前把手和龙尾后把手。"
                        "numeric_results 顶层必须写入 max_distance_residual_m、"
                        "initial_head_radius_m、initial_tail_radius_m。"
                        if source_text
                        and subtask_title == "ques1"
                        and "等距螺线" in source_text
                        and "顺时针盘入" in source_text
                        and re.search(r"各把手中心均位于螺线上", source_text)
                        else ""
                    )
                    + (
                        format_source_figure_requirements(source_text)
                        + "若触发关键图示要求，必须实际读取官方 PDF/图片，并在 "
                        "data_scope.source_figures JSON 数组中逐图记录 "
                        "file、page（从1开始）、figure、facts；正确形态是 "
                        '[{"file":"A题.pdf","page":2,"figure":4,'
                        '"facts":["命名点相对坐标轴/内外端/方向的明确关系"]}]，'
                        "不得写成以 figure_4 为键的对象；仅写‘已核验’不算事实。"
                        if source_text and subtask_title == "eda"
                        else ""
                    )
                ),
            }
        )

        retry_count = 0
        total_execution_errors = 0
        last_error_message = ""
        successful_execution = False
        last_execution_output = ""
        eda_repair_required = False
        eda_repair_executions = 0

        async def finalize_success(completion_text: str) -> CoderToWriter:
            evidence_name, evidence = load_evidence_contract(
                self.work_dir,
                subtask_title,
                source_text=source_text,
            )
            for template_name, snapshot in template_snapshots.items():
                validate_spreadsheet_template_output(
                    Path(self.work_dir) / template_name,
                    snapshot,
                    source_text=source_text,
                    subtask_title=subtask_title,
                )
            created_images = await self.code_interpreter.get_created_images(
                subtask_title
            )
            created_images = [
                image
                for image in created_images
                if Path(image).name not in source_inspection_images
            ]
            return CoderToWriter(
                code_response=(
                    f"{completion_text or '代码阶段完成'}\n"
                    f"已验证证据合同：{json.dumps(evidence, ensure_ascii=False)}"
                ),
                code_output=last_execution_output,
                created_images=created_images,
                artifacts=[
                    *created_images,
                    evidence_name,
                    *template_snapshots,
                ],
                execution_attempts=total_execution_errors + 1,
                status="success",
            )

        while True:
            if (
                subtask_title == "eda"
                and eda_repair_required
                and eda_repair_executions >= 1
            ):
                logger.error("EDA 证据合同定向修复机会已用尽")
                return CoderToWriter(
                    status="failed",
                    error=(
                        "EDA 证据合同未在一次定向修复内通过质量门禁；"
                        "已停止跨问求解和继续扫描"
                    ),
                    execution_attempts=total_execution_errors,
                )
            if self.max_retries is not None and retry_count >= self.max_retries:
                logger.error(f"超过最大尝试次数: {self.max_retries}")
                await redis_manager.publish_message(
                    self.task_id,
                    SystemMessage(content="超过最大尝试次数", type="error"),
                )
                logger.warning(
                    f"任务失败，超过最大尝试次数{self.max_retries}, 最后错误信息: {last_error_message}"
                )
                return CoderToWriter(
                    status="failed",
                    error=f"任务失败，超过最大尝试次数 {self.max_retries}: {last_error_message}",
                    execution_attempts=total_execution_errors,
                )

            if (
                self.max_chat_turns is not None
                and self.current_chat_turns >= self.max_chat_turns
            ):
                logger.error(f"超过最大聊天次数: {self.max_chat_turns}")
                await redis_manager.publish_message(
                    self.task_id,
                    SystemMessage(content="超过最大聊天次数", type="error"),
                )
                return CoderToWriter(
                    status="failed",
                    error=f"超过最大聊天次数 {self.max_chat_turns}，代码阶段未完成",
                    execution_attempts=total_execution_errors,
                )

            self.current_chat_turns += 1
            logger.info(f"当前对话轮次: {self.current_chat_turns}")

            try:
                response = await self._chat(
                    history=self.chat_history,
                    tools=tools,
                    tool_choice="auto",
                    agent_name=self.__class__.__name__,
                )

                # 如果有工具调用
                if response.tool_calls:
                    logger.info("检测到工具调用")
                    tool_call = response.tool_calls[0]
                    tool_id = tool_call.id

                    if tool_call.name == "execute_code":
                        logger.info(f"调用工具: {tool_call.name}")
                        await redis_manager.publish_message(
                            self.task_id,
                            SystemMessage(content=f"代码手调用{tool_call.name}工具"),
                        )

                        try:
                            code = json.loads(tool_call.arguments)["code"]
                        except (TypeError, KeyError, json.JSONDecodeError) as exc:
                            retry_count += 1
                            total_execution_errors += 1
                            last_error_message = f"execute_code 参数无效: {exc}"
                            await self.append_chat_history(
                                {"role": "user", "content": last_error_message}
                            )
                            continue

                        if subtask_title == "eda" and eda_repair_required:
                            eda_repair_executions += 1

                        reads_output_template = bool(
                            subtask_title == "eda"
                            and re.search(
                                r"(?:read_excel|ExcelFile|load_workbook)", code
                            )
                            and any(name in code for name in output_template_names)
                        )
                        if reads_output_template:
                            template_inspection_calls += 1
                            if template_inspection_calls > 2:
                                await self.append_chat_history(
                                    {
                                        "role": "user",
                                        "content": (
                                            "程序拒绝第 3 次输出模板结构检查。"
                                            "请使用已提供的结构摘要，立即转入来源参数、"
                                            "几何和量纲审计。"
                                        ),
                                    }
                                )
                                continue

                        source_figure_inspection = (
                            subtask_title == "eda"
                            and is_source_figure_inspection_code(code)
                        )
                        if source_figure_inspection:
                            source_figure_inspection_calls += 1
                            if source_figure_inspection_calls > 2:
                                await self.append_chat_history(
                                    {
                                        "role": "user",
                                        "content": (
                                            "程序拒绝第 3 次关键题图检查。请使用前两次已提取的"
                                            "文件、页码、图号与方位/坐标事实，立即写入证据合同；"
                                            "不得继续生成或分析派生图片。"
                                        ),
                                    }
                                )
                                continue

                        await redis_manager.publish_message(
                            self.task_id,
                            InterpreterMessage(
                                input={"code": code},
                            ),
                        )

                        # 更新对话历史 - 添加助手的响应
                        assistant_msg: dict = {
                            "role": "assistant",
                            "content": response.content,
                        }
                        if response.reasoning_content:
                            assistant_msg["reasoning_content"] = (
                                response.reasoning_content
                            )
                        if response.tool_calls:
                            assistant_msg["tool_calls"] = [
                                {
                                    "id": tc.id,
                                    "type": "function",
                                    "function": {
                                        "name": tc.name,
                                        "arguments": tc.arguments,
                                    },
                                }
                                for tc in response.tool_calls
                            ]
                        await self.append_chat_history(assistant_msg)

                        # 执行工具调用
                        logger.info("执行工具调用")
                        images_before_execution = {
                            path.name
                            for path in Path(self.work_dir).iterdir()
                            if path.is_file()
                            and path.suffix.lower()
                            in {".png", ".jpg", ".jpeg", ".pdf", ".svg"}
                        }
                        (
                            text_to_gpt,
                            error_occurred,
                            error_message,
                        ) = await self.code_interpreter.execute_code(code)
                        if source_figure_inspection:
                            images_after_execution = {
                                path.name
                                for path in Path(self.work_dir).iterdir()
                                if path.is_file()
                                and path.suffix.lower()
                                in {".png", ".jpg", ".jpeg", ".pdf", ".svg"}
                            }
                            source_inspection_images.update(
                                images_after_execution - images_before_execution
                            )

                        # 添加工具执行结果
                        if error_occurred:
                            # 即使发生错误也要添加tool响应
                            await self.append_chat_history(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_id,
                                    "name": "execute_code",
                                    "content": error_message,
                                }
                            )

                            logger.warning(f"代码执行错误: {error_message}")
                            retry_count += 1
                            total_execution_errors += 1
                            logger.info(
                                f"当前尝试次:{retry_count} / {self.max_retries}"
                            )
                            last_error_message = error_message
                            reflection_prompt = get_reflection_prompt(
                                error_message, code
                            )

                            await redis_manager.publish_message(
                                self.task_id,
                                SystemMessage(
                                    content="代码手反思纠正错误", type="error"
                                ),
                            )

                            await self.append_chat_history(
                                {"role": "user", "content": reflection_prompt}
                            )
                            continue
                        else:
                            # 成功执行的tool响应
                            await self.append_chat_history(
                                {
                                    "role": "tool",
                                    "tool_call_id": tool_id,
                                    "name": "execute_code",
                                    "content": text_to_gpt,
                                }
                            )
                            last_execution_output = (
                                text_to_gpt or "代码执行成功，但解释器未返回文本输出"
                            )
                            if has_unresolved_solver_failure(last_execution_output):
                                retry_count += 1
                                total_execution_errors += 1
                                successful_execution = False
                                last_error_message = (
                                    "求解输出仍含未解决的无解、求根失败或回退警告"
                                )
                                await self.append_chat_history(
                                    {
                                        "role": "user",
                                        "content": (
                                            f"{last_error_message}。不得用缩半、置零、"
                                            "上一时刻值或其他假回退继续并声明成功；"
                                            "请修正参数方向/括区间，或明确返回失败。"
                                        ),
                                    }
                                )
                                continue
                            successful_execution = True
                            retry_count = 0
                            if (Path(self.work_dir) / evidence_file).is_file():
                                try:
                                    return await finalize_success(response.content)
                                except QualityGateError as exc:
                                    if subtask_title == "eda":
                                        eda_repair_required = True
                                    await self.append_chat_history(
                                        {
                                            "role": "user",
                                            "content": (
                                                f"子任务尚未完成，质量门禁失败：{exc}。"
                                                + (
                                                    "EDA 只允许再执行一次定向修复："
                                                    "仅修正证据合同中门禁指明的来源事实，"
                                                    "不得求解任何 quesN、候选扫描、优化或仿真；"
                                                    if subtask_title == "eda"
                                                    else "请继续执行代码修正证据合同或模板；"
                                                )
                                                + "不得只用文字声称完成。"
                                            ),
                                        }
                                    )
                            continue
                else:
                    # 没有工具调用，表示任务完成
                    logger.info("没有工具调用，任务完成")
                    if not successful_execution:
                        return CoderToWriter(
                            status="failed",
                            error="代码手未调用 execute_code，拒绝把未执行文本交给论文手",
                            execution_attempts=total_execution_errors,
                        )
                    try:
                        return await finalize_success(response.content)
                    except QualityGateError as exc:
                        if subtask_title == "eda":
                            eda_repair_required = True
                        await self.append_chat_history(
                            {
                                "role": "user",
                                "content": (
                                    f"子任务尚未完成，质量门禁失败：{exc}。"
                                    + (
                                        "EDA 只允许再执行一次定向修复："
                                        "仅修正证据合同中门禁指明的来源事实，"
                                        "不得求解任何 quesN、候选扫描、优化或仿真；"
                                        if subtask_title == "eda"
                                        else "请继续执行代码补齐真实数值、验证证据和模板回填；"
                                    )
                                    + "不得只用文字声称完成。"
                                ),
                            }
                        )
                        continue

            except Exception as e:
                logger.error(f"执行过程中发生异常: {str(e)}")
                retry_count += 1
                total_execution_errors += 1
                last_error_message = str(e)
                continue
            logger.info(f"{self.__class__.__name__}:完成:执行子任务: {subtask_title}")
