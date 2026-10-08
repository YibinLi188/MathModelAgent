"""Modeler structure-validation retry regression tests."""

import asyncio
import json
from types import SimpleNamespace

from app.core.agents.modeler_agent import ModelerAgent
from app.schemas.A2A import CoordinatorToModeler


class _TwoResponseModel:
    def __init__(self) -> None:
        self.calls = 0

    async def chat(self, **_kwargs):
        self.calls += 1
        solution = {
            "eda": "source_parameter_audit: official inputs checked",
            "ques1": "model, solve, verify and report",
            "sensitivity_analysis": "recompute the main result",
        }
        if self.calls == 1:
            solution["ques1_note"] = "placeholder"
        return SimpleNamespace(
            content=json.dumps(solution),
            reasoning_content=None,
        )


class _FigureResponseModel:
    def __init__(self) -> None:
        self.calls = 0

    async def chat(self, **_kwargs):
        self.calls += 1
        return SimpleNamespace(
            content=json.dumps(
                {
                    "eda": "source_parameter_audit: official inputs checked",
                    "ques1": "model, solve, verify and report",
                    "sensitivity_analysis": "recompute with a finer grid",
                }
            ),
            reasoning_content=None,
        )


def test_modeler_retries_unknown_solution_key_instead_of_aborting():
    model = _TwoResponseModel()
    agent = ModelerAgent("fixture-task", model)  # type: ignore[arg-type]
    coordinator = CoordinatorToModeler(
        questions={"ques_count": 1, "ques1": "solve the official task"},
        ques_count=1,
    )

    result = asyncio.run(
        agent.run(coordinator, authoritative_source_text="official task statement")
    )

    assert model.calls == 2
    assert set(result.questions_solution) == {
        "eda",
        "ques1",
        "sensitivity_analysis",
    }
    assert any(
        "删除占位、note、说明等其他键" in message.get("content", "")
        for message in agent.chat_history
    )
    assert any(
        "不得输出任何自我纠错" in message.get("content", "")
        and "eda 不超过1600字" in message.get("content", "")
        for message in agent.chat_history
    )


def test_modeler_injects_deterministic_source_figure_handoff():
    model = _FigureResponseModel()
    agent = ModelerAgent("figure-fixture-task", model)  # type: ignore[arg-type]
    coordinator = CoordinatorToModeler(
        questions={"ques_count": 1, "ques1": "initial point is in figure 4"},
        ques_count=1,
    )

    result = asyncio.run(
        agent.run(
            coordinator,
            authoritative_source_text="问题 1 初始时位于A点（见图4）。",
        )
    )

    assert model.calls == 1
    assert "source_figure_required" in result.questions_solution["eda"]
    assert '"figure":4' in result.questions_solution["eda"]
