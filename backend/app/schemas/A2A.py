"""Agent 间通信数据模型定义。

这些模型是阶段之间的质量边界：下游只能消费明确标记为成功、带有执行
证据的结果，不能把错误文本当成论文事实。
"""

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CoordinatorToModeler(BaseModel):
    """协调者传递给建模手的数据结构。"""

    model_config = ConfigDict(extra="forbid")
    questions: dict
    ques_count: int = Field(ge=1)

    @model_validator(mode="after")
    def validate_question_keys(self):
        question_keys = sorted(
            key for key in self.questions if re.fullmatch(r"ques\d+", key)
        )
        expected = [f"ques{i}" for i in range(1, self.ques_count + 1)]
        missing = [key for key in expected if key not in question_keys]
        if missing:
            raise ValueError(f"协调结果缺少问题字段: {missing}")
        return self


class ModelerToCoder(BaseModel):
    """建模手传递给代码手的数据结构。"""

    model_config = ConfigDict(extra="forbid")
    questions_solution: dict[str, str]

    @field_validator("questions_solution")
    @classmethod
    def validate_solutions(cls, value: dict[str, str]):
        allowed = re.compile(r"^(eda|sensitivity_analysis|ques\d+)$")
        for key, text in value.items():
            if not allowed.fullmatch(key):
                raise ValueError(f"未知建模方案字段: {key}")
            if not isinstance(text, str) or not text.strip():
                raise ValueError(f"建模方案 {key} 不能为空")
        return value


class CoderToWriter(BaseModel):
    """代码手传递给写作手的数据结构。"""
    model_config = ConfigDict(extra="forbid")
    code_response: str | None = None
    code_output: str | None = None
    created_images: list[str] = Field(default_factory=list)
    status: Literal["success", "failed"] = "success"
    error: str | None = None
    execution_attempts: int = Field(default=0, ge=0)
    artifacts: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_status(self):
        if self.status == "success" and not self.code_output and not self.code_response:
            raise ValueError("成功的代码结果必须包含代码输出或结果摘要")
        if self.status == "failed" and not self.error:
            raise ValueError("失败的代码结果必须包含 error")
        return self


class WriterResponse(BaseModel):
    """写作手的响应数据结构。"""
    model_config = ConfigDict(extra="forbid")
    response_content: Any
    footnotes: list[tuple[str, str]] | None = None
