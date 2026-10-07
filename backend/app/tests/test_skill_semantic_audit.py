"""Regression checks for the modeling objective-semantics hard gate."""

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[3]


def test_writing_and_verification_skills_require_objective_semantics_audit():
    reference = REPO_ROOT / "skills" / "_references" / "objective_semantics_audit.md"
    writing = (REPO_ROOT / "skills" / "5writing" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    verification = (REPO_ROOT / "skills" / "6verity" / "SKILL.md").read_text(
        encoding="utf-8"
    )

    assert reference.is_file()
    assert "objective_semantics_audit.md" in writing
    assert "objective_semantics_audit.md" in verification


def test_objective_semantics_reference_covers_incremental_cost_and_unit_cases():
    text = (
        REPO_ROOT / "skills" / "_references" / "objective_semantics_audit.md"
    ).read_text(encoding="utf-8")

    assert "边际" in text
    assert "退款" in text
    assert "违约" in text
    assert "一单位测试" in text
    assert "基准费用" in text
