"""建模手 Agent 模块，负责分析问题并制定建模方案。"""

import asyncio
from app.core.agents.agent import Agent
from app.core.llm.llm import LLM
from app.core.prompts import MODELER_PROMPT
from app.schemas.A2A import CoordinatorToModeler, ModelerToCoder
from app.core.quality_gates import (
    QualityGateError,
    derive_source_figure_requirements,
    format_source_guardrails,
    validate_modeler_result,
)
from app.utils.log_util import logger
import json
from icecream import ic  # type: ignore[import-unresolved]
from pydantic import ValidationError

MAX_JSON_RETRIES = 4


def repair_json(json_str: str) -> dict | None:
    """尝试修复 LLM 输出的格式错误的 JSON。

    Args:
        json_str: 可能包含格式错误的 JSON 字符串。

    Returns:
        修复后的字典，无法修复时返回 None。
    """
    json_str = json_str.replace("```json", "").replace("```", "").strip()

    # Try direct parse first
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        pass

    # 允许 JSON 前后存在少量说明，但不再用正则猜测字段内容。
    try:
        start = json_str.find("{")
        if start >= 0:
            value, _ = json.JSONDecoder().raw_decode(json_str[start:])
            if isinstance(value, dict):
                return value
    except json.JSONDecodeError:
        pass

    return None


class ModelerAgent(Agent):
    """建模手 Agent，分析问题类型并制定建模方案、求解方法和可视化策略。"""

    def __init__(
        self,
        task_id: str,
        model: LLM,
        context_window: int = 128000,
        cancel_event: asyncio.Event | None = None,
    ) -> None:
        super().__init__(task_id, model, context_window, cancel_event=cancel_event)
        self.system_prompt = MODELER_PROMPT

    async def run(
        self,
        coordinator_to_modeler: CoordinatorToModeler,
        authoritative_source_text: str | None = None,
    ) -> ModelerToCoder:  # type: ignore[reportIncompatibleMethodOverride]
        """根据协调者拆解的问题生成建模方案。

        Args:
            coordinator_to_modeler: 协调者传递的结构化问题信息。

        Returns:
            ModelerToCoder 对象，包含各问题的建模解决方案。
        """
        await self.append_chat_history(
            {"role": "system", "content": self.system_prompt}
        )
        question_keys = {
            key
            for key in coordinator_to_modeler.questions
            if key.startswith("ques") and key != "ques_count"
        }
        coordinator_outline = json.dumps(
            coordinator_to_modeler.questions, ensure_ascii=False
        )
        source_text = authoritative_source_text or coordinator_outline
        await self.append_chat_history(
            {
                "role": "user",
                "content": (
                    "冻结的用户原始题面（唯一事实来源，不得被重述覆盖）：\n"
                    + source_text
                    + "\n\nCoordinator 结构化索引（只用于定位子问题，若有删减或冲突以原始题面为准）：\n"
                    + coordinator_outline
                    + "\n\n"
                    + format_source_guardrails(source_text)
                    + "\n请将这些程序派生的题面不变量作为方案前置约束，"
                    "不得在同一输出中又给出相矛盾的节点数或连接点距离语义。"
                ),
            }
        )

        attempt = 0
        while attempt < MAX_JSON_RETRIES:
            response = await self._chat(
                history=self.chat_history,
                agent_name=self.__class__.__name__,
            )

            json_str = response.content
            if not json_str:
                raise ValueError("返回的 JSON 字符串为空，请检查输入内容。")

            questions_solution = repair_json(json_str)
            if questions_solution:
                figure_requirements = derive_source_figure_requirements(source_text)
                serialized_solution = json.dumps(questions_solution, ensure_ascii=False)
                if (
                    figure_requirements
                    and "source_figure_required" not in serialized_solution
                    and isinstance(questions_solution.get("eda"), str)
                ):
                    questions_solution["eda"] += (
                        " source_figure_required: 代码阶段必须核验官方关键图示："
                        + json.dumps(
                            figure_requirements,
                            ensure_ascii=False,
                            separators=(",", ":"),
                        )
                    )
                ic(questions_solution)
                try:
                    result = ModelerToCoder(questions_solution=questions_solution)
                    validate_modeler_result(
                        result, question_keys, source_text=source_text
                    )
                except (QualityGateError, ValidationError) as exc:
                    attempt += 1
                    logger.warning(
                        f"建模方案未通过结构/质量门禁 (第{attempt}/"
                        f"{MAX_JSON_RETRIES}次): {exc}"
                    )
                    await self.append_chat_history(
                        {"role": "assistant", "content": json_str}
                    )
                    await self.append_chat_history(
                        {
                            "role": "user",
                            "content": (
                                f"建模方案未通过结构/质量门禁：{exc}。"
                                "顶层键只允许 eda、"
                                f"{', '.join(sorted(question_keys))} 和 "
                                "sensitivity_analysis；删除占位、note、说明等其他键。"
                                "不得输出任何自我纠错、推理争论或‘已删除某键’之类的过程文字；"
                                "eda 不超过1600字，每个 quesN 和 sensitivity_analysis "
                                "分别不超过1200字。"
                                "请只按题面原值修正来源参数、实体--节点拓扑和派生公式，"
                                "然后重新输出完整、简洁 JSON；必须包含 eda、"
                                "所有 quesN 和 sensitivity_analysis，不要输出自我纠错过程。"
                                "再次逐项执行以下程序前置合同："
                                + format_source_guardrails(source_text)
                            ),
                        }
                    )
                    continue
                else:
                    return result

            attempt += 1
            logger.warning(
                f"JSON 解析失败 (第{attempt}/{MAX_JSON_RETRIES}次)，请求模型重新生成"
            )
            retry_msg: dict = {"role": "assistant", "content": json_str}
            if response.reasoning_content:
                retry_msg["reasoning_content"] = response.reasoning_content
            await self.append_chat_history(retry_msg)
            await self.append_chat_history(
                {
                    "role": "user",
                    "content": (
                        "你返回的 JSON 格式有误或被过长内容截断。"
                        "请从头输出单层、完整、简洁 JSON，必须包含 eda、"
                        "所有 quesN 和 sensitivity_analysis；每个值不超过约 1200 个字，"
                        "不要输出自我纠错过程，字符串内双引号必须转义。"
                    ),
                }
            )

        raise ValueError("ModelerAgent JSON 解析重试次数耗尽")
