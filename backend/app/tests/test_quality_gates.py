"""质量契约回归测试。"""

from pathlib import Path

import pytest

from app.core.quality_gates import (
    QualityGateError,
    validate_coder_result,
    validate_competition_paper_text,
    validate_modeler_result,
    validate_writer_result,
)
from app.models.user_output import UserOutput
from app.core.prompts.coder import CODER_PROMPT
from app.core.prompts.modeler import MODELER_PROMPT
from app.core.prompts.writer import get_writer_prompt
from app.schemas.A2A import CoderToWriter, ModelerToCoder, WriterResponse
from app.schemas.enums import FormatOutPut


def test_modeler_requires_all_solution_sections():
    result = ModelerToCoder(
        questions_solution={"eda": "ok", "ques1": "ok", "sensitivity_analysis": "ok"}
    )
    validate_modeler_result(result, {"ques1"})
    with pytest.raises(QualityGateError):
        validate_modeler_result(result, {"ques1", "ques2"})


def test_failed_coder_cannot_cross_gate(tmp_path: Path):
    result = CoderToWriter(status="failed", error="syntax error")
    with pytest.raises(QualityGateError):
        validate_coder_result(result, tmp_path)


def test_coder_artifact_must_exist(tmp_path: Path):
    result = CoderToWriter(
        status="success", code_output="ok", artifacts=["results.json"]
    )
    with pytest.raises(QualityGateError):
        validate_coder_result(result, tmp_path)


def test_writer_rejects_placeholders():
    with pytest.raises(QualityGateError):
        validate_writer_result(WriterResponse(response_content="待补充"))


@pytest.mark.parametrize(
    "text",
    [
        "论文生成时间：2026-08-13",
        "Agent 版本：v2",
        "本文的核心优势不是算法名称，而是证据链。",
    ],
)
def test_writer_rejects_generation_meta_text(text: str):
    with pytest.raises(QualityGateError):
        validate_writer_result(
            WriterResponse(response_content=text), section_name="firstPage"
        )


def test_paper_rejects_colored_heading():
    with pytest.raises(QualityGateError):
        validate_competition_paper_text(
            r"\section{\textcolor{blue}{问题分析}}"
        )


def test_paper_rejects_duplicate_reference_heading():
    with pytest.raises(QualityGateError):
        validate_competition_paper_text("## 参考文献\n正文\n# 参考文献")


def test_normal_competition_abstract_passes():
    validate_writer_result(
        WriterResponse(
            response_content=(
                "# 板凳龙运动轨迹与调头路径模型\n\n"
                "摘要：建立等距约束模型，求得首次碰撞时刻并完成全区间复核。"
            )
        ),
        section_name="firstPage",
    )


def test_prompts_route_abc_and_require_domain_audit():
    assert "A/B/C 差异化先验" in MODELER_PROMPT
    assert "content_override" in MODELER_PROMPT
    assert "连续域与全题覆盖验收" in CODER_PROMPT
    assert "多个相互分离的候选峰" in CODER_PROMPT


def test_writer_prompt_avoids_template_bloat():
    prompt = get_writer_prompt(FormatOutPut.LaTeX)
    assert "全文合计：13-18张" not in prompt
    assert "每幅图表至少配3行" not in prompt
    assert "各级标题使用黑色" in prompt
    assert "生成/验收时间" in prompt


def test_repeated_reference_keeps_one_number(tmp_path: Path):
    output = UserOutput(str(tmp_path), ques_count=1)
    first = WriterResponse(response_content="结论 {[^1]: Source}")
    second = WriterResponse(response_content="再次引用 {[^1]: Source}")
    output.set_res("firstPage", first)
    output.set_res("ques1", second)
    # 完整顺序所需的空章节以空字符串补齐。
    for key in output.seq:
        output.res.setdefault(key, {"response_content": "", "footnotes": None})
    text = output.get_result_to_save()
    assert text.count("[^1]") == 3  # 正文两次 + 文末脚注定义一次
    assert text.count("Source") == 1
