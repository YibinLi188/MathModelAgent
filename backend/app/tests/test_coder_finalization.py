"""Coder completion-order regression tests."""

import asyncio
import json
from pathlib import Path
from types import SimpleNamespace

from app.config.setting import ApiType
from app.core.agents import coder_agent as coder_agent_module
from app.core.agents.coder_agent import CoderAgent
from app.core.quality_gates import QualityGateError
from app.services.redis_manager import redis_manager


class _OneTurnModel:
    api_type = ApiType.OPENAI_CHAT

    def __init__(self) -> None:
        self.calls = 0

    async def chat(self, **_kwargs):
        self.calls += 1
        tool_call = SimpleNamespace(
            id="tool-1",
            name="execute_code",
            arguments=json.dumps({"code": "write final evidence"}),
        )
        return SimpleNamespace(
            content="",
            reasoning_content=None,
            tool_calls=[tool_call],
        )


class _SourceInspectionModel(_OneTurnModel):
    async def chat(self, **_kwargs):
        response = await super().chat(**_kwargs)
        response.tool_calls[0].arguments = json.dumps(
            {"code": "doc = fitz.open('official.pdf')"}
        )
        return response


class _ContractWritingInterpreter:
    def __init__(self, work_dir: Path) -> None:
        self.work_dir = work_dir
        self.calls = 0

    def add_section(self, _section: str) -> None:
        pass

    async def execute_code(self, _code: str):
        self.calls += 1
        contract = {
            "status": "success",
            "subtask": "eda",
            "data_scope": "official statement",
            "assumptions": [],
            "model": "fixture",
            "numeric_results": {"value": 1.0},
            "validation": {"passed": True, "checks": ["recomputed"]},
            "conclusion_bounds": "fixture only",
        }
        (self.work_dir / "results_eda.json").write_text(
            json.dumps(contract), encoding="utf-8"
        )
        return "contract written", False, ""

    async def get_created_images(self, _section: str):
        return []


class _WarningContractInterpreter(_ContractWritingInterpreter):
    async def execute_code(self, code: str):
        await super().execute_code(code)
        return (
            "WARNING: 无法在θ区间找到距离1.65m的解，使用回退值",
            False,
            "",
        )


class _InspectionImageInterpreter(_ContractWritingInterpreter):
    async def execute_code(self, code: str):
        result = await super().execute_code(code)
        (self.work_dir / "page2_fig4.png").write_bytes(b"inspection fixture")
        return result

    async def get_created_images(self, _section: str):
        return ["page2_fig4.png"]


def test_coder_accepts_contract_written_on_last_chat_turn(tmp_path: Path, monkeypatch):
    async def publish_message(_task_id: str, _message: object) -> None:
        pass

    monkeypatch.setattr(redis_manager, "publish_message", publish_message)
    model = _OneTurnModel()
    agent = CoderAgent(
        "fixture-task",
        model,  # type: ignore[arg-type]
        str(tmp_path),
        max_chat_turns=1,
        code_interpreter=_ContractWritingInterpreter(tmp_path),  # type: ignore[arg-type]
    )
    result = asyncio.run(agent.run("run fixture", "eda"))
    assert result.status == "success"
    assert model.calls == 1


def test_coder_rejects_contract_after_solver_failure_warning(
    tmp_path: Path, monkeypatch
):
    async def publish_message(_task_id: str, _message: object) -> None:
        pass

    monkeypatch.setattr(redis_manager, "publish_message", publish_message)
    model = _OneTurnModel()
    agent = CoderAgent(
        "fixture-task",
        model,  # type: ignore[arg-type]
        str(tmp_path),
        max_chat_turns=1,
        code_interpreter=_WarningContractInterpreter(tmp_path),  # type: ignore[arg-type]
    )
    result = asyncio.run(agent.run("run fixture", "eda"))
    assert result.status == "failed"
    assert "最大聊天次数" in (result.error or "")


def test_source_inspection_image_is_not_sent_to_writer(tmp_path: Path, monkeypatch):
    async def publish_message(_task_id: str, _message: object) -> None:
        pass

    monkeypatch.setattr(redis_manager, "publish_message", publish_message)
    agent = CoderAgent(
        "fixture-task",
        _SourceInspectionModel(),  # type: ignore[arg-type]
        str(tmp_path),
        max_chat_turns=1,
        code_interpreter=_InspectionImageInterpreter(tmp_path),  # type: ignore[arg-type]
    )
    result = asyncio.run(agent.run("inspect official figure", "eda"))
    assert result.status == "success"
    assert result.created_images == []
    assert "page2_fig4.png" not in result.artifacts


def test_eda_stops_after_one_failed_targeted_contract_repair(
    tmp_path: Path, monkeypatch
):
    async def publish_message(_task_id: str, _message: object) -> None:
        pass

    def reject_contract(*_args, **_kwargs):
        raise QualityGateError("图 4 的命名点坐标关系不一致")

    monkeypatch.setattr(redis_manager, "publish_message", publish_message)
    monkeypatch.setattr(coder_agent_module, "load_evidence_contract", reject_contract)
    model = _OneTurnModel()
    interpreter = _ContractWritingInterpreter(tmp_path)
    agent = CoderAgent(
        "fixture-task",
        model,  # type: ignore[arg-type]
        str(tmp_path),
        max_chat_turns=10,
        code_interpreter=interpreter,  # type: ignore[arg-type]
    )

    result = asyncio.run(agent.run("audit fixture", "eda"))

    assert result.status == "failed"
    assert "一次定向修复" in (result.error or "")
    assert model.calls == 2
    assert interpreter.calls == 2


def test_eda_executes_one_targeted_repair_before_accepting_contract(
    tmp_path: Path, monkeypatch
):
    async def publish_message(_task_id: str, _message: object) -> None:
        pass

    gate_calls = 0

    def accept_repaired_contract(*_args, **_kwargs):
        nonlocal gate_calls
        gate_calls += 1
        if gate_calls == 1:
            raise QualityGateError("图 4 页码错误")
        return "results_eda.json", {"status": "success"}

    monkeypatch.setattr(redis_manager, "publish_message", publish_message)
    monkeypatch.setattr(
        coder_agent_module, "load_evidence_contract", accept_repaired_contract
    )
    model = _OneTurnModel()
    interpreter = _ContractWritingInterpreter(tmp_path)
    agent = CoderAgent(
        "fixture-task",
        model,  # type: ignore[arg-type]
        str(tmp_path),
        max_chat_turns=10,
        code_interpreter=interpreter,  # type: ignore[arg-type]
    )

    result = asyncio.run(agent.run("audit fixture", "eda"))

    assert result.status == "success"
    assert model.calls == 2
    assert interpreter.calls == 2
