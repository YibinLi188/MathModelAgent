"""质量契约回归测试。"""

from pathlib import Path

import pytest

from app.core.quality_gates import (
    QualityGateError,
    validate_coder_result,
    validate_modeler_result,
    validate_writer_result,
)
from app.models.user_output import UserOutput
from app.schemas.A2A import CoderToWriter, ModelerToCoder, WriterResponse


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
