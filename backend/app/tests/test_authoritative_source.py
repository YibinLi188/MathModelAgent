"""The original user statement must remain the downstream evidence source."""

from app.core.flows import Flows
from app.schemas.A2A import ModelerToCoder


def test_solution_flows_do_not_let_coordinator_omit_source_fact():
    original = "初始时端点位于第16圈A点处（见图4）。"
    normalized = {
        "title": "fixture",
        "background": "fixture",
        "ques_count": 1,
        "ques1": "初始时端点位于第16圈A点处。",
    }
    modeler = ModelerToCoder(
        questions_solution={
            "eda": "source_parameter_audit: fixture",
            "ques1": "fixture",
            "sensitivity_analysis": "fixture",
        }
    )

    solution_flows = Flows(
        normalized,
        authoritative_source_text=original,
    ).get_solution_flows(normalized, modeler)

    assert solution_flows["eda"]["source_text"] == original
    assert solution_flows["ques1"]["source_text"] == original
    assert original in solution_flows["eda"]["coder_prompt"]
    assert "见图4" in solution_flows["ques1"]["coder_prompt"]
