"""阶段质量闸门。

质量闸门不判断模型优劣，而是阻止明显不完整或不可审计的结果继续流向
论文阶段。所有失败都以可读错误返回，便于前端和验收报告处理。
"""

from __future__ import annotations

import re
from pathlib import Path

from app.schemas.A2A import CoderToWriter, ModelerToCoder, WriterResponse


class QualityGateError(ValueError):
    """结果未满足阶段契约。"""


def validate_modeler_result(result: ModelerToCoder, question_keys: set[str]) -> None:
    """确保每个题目都有非空建模方案。"""
    required = {"eda", "sensitivity_analysis", *question_keys}
    missing = sorted(required - set(result.questions_solution))
    if missing:
        raise QualityGateError(f"建模方案缺少字段: {missing}")
    invalid = [
        key for key in result.questions_solution
        if not re.fullmatch(r"^(eda|sensitivity_analysis|ques\d+)$", key)
    ]
    if invalid:
        raise QualityGateError(f"建模方案包含未知字段: {invalid}")


def validate_coder_result(result: CoderToWriter, work_dir: str | Path) -> None:
    """阻断失败、空结果和不存在的图表证据进入 Writer。"""
    if result.status != "success":
        raise QualityGateError(result.error or "代码阶段失败")
    if not (result.code_output or result.code_response):
        raise QualityGateError("代码阶段没有输出结果")
    root = Path(work_dir).resolve()
    for artifact in [*result.created_images, *result.artifacts]:
        path = (root / artifact).resolve()
        if root not in path.parents and path != root:
            raise QualityGateError(f"产物路径越界: {artifact}")
        if not path.exists():
            raise QualityGateError(f"代码声明的产物不存在: {artifact}")


def validate_writer_result(result: WriterResponse) -> None:
    """确保 Writer 至少返回可保存的非空正文。"""
    text = result.response_content
    if not isinstance(text, str) or not text.strip():
        raise QualityGateError("论文阶段返回空正文")
    if re.search(
        r"(?:TODO|PLACEHOLDER|待补充|待续写|搜索文献失败|执行过程中遇到错误)",
        text,
        re.IGNORECASE,
    ):
        raise QualityGateError("论文正文包含占位符或 Agent 错误信息")
