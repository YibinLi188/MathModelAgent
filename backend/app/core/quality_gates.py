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


def validate_competition_paper_text(
    text: str, *, section_name: str | None = None
) -> None:
    """拦截竞赛论文中的生成元话语和明显模板污染。"""
    meta_patterns = (
        r"(?:文档|论文|报告|PDF)?\s*(?:生成|验收)时间\s*[:：]",
        r"(?:Agent|模型|系统)\s*版本\s*[:：]",
        r"(?:由|使用).{0,12}(?:AI|Agent|大模型).{0,8}(?:自动)?(?:生成|撰写)",
        r"自动生成(?:的)?(?:论文|报告|文档)",
        r"本文的核心优势不是算法名称",
        r"(?:官方|标准)结果模板的写法",
        r"结果(?:仅)?另行保存",
    )
    for pattern in meta_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            label = section_name or "正文"
            raise QualityGateError(f"{label} 包含生成过程、自我评价或模板元话语")

    for line in text.splitlines():
        is_heading = re.search(
            r"(?:\\(?:title|section|subsection|subsubsection)\b|^\s*#{1,6}\s+)",
            line,
        )
        has_color = re.search(
            r"(?:\\(?:color|textcolor|colorbox)\b|\bcolor\s*=|<font[^>]*\bcolor)",
            line,
            re.IGNORECASE,
        )
        if is_heading and has_color:
            raise QualityGateError("论文标题或章节标题包含非模板要求的显式颜色")

    reference_headings = re.findall(
        r"(?m)^\s*(?:#{1,6}\s*|\\(?:section\*?|chapter\*?)\s*\{)参考文献\}?\s*$",
        text,
    )
    if len(reference_headings) > 1:
        raise QualityGateError("论文包含重复的参考文献标题")


def validate_writer_result(
    result: WriterResponse, *, section_name: str | None = None
) -> None:
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
    validate_competition_paper_text(text, section_name=section_name)
