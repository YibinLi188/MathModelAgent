#!/usr/bin/env python3
"""Regression tests for explicit structured-result contract discovery."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("validate_results_contract.py")


def valid_contract(task: str = "ques1") -> dict:
    return {
        "schema_version": "1.2",
        "status": "success",
        "task": task,
        "data_hashes": ["sha256:test"],
        "sample": {"n_total": 1},
        "metrics": {"value": 1.0},
        "metric_semantics": {
            "value": {
                "quantity": "test quantity",
                "unit": "1",
                "numerator": "one",
                "denominator": "one",
            }
        },
        "parameters": {},
        "artifacts": ["results/evidence.txt"],
        "validation": {
            "independent_recompute": True,
            "independent_delta": 0.0,
            "tolerance": 1e-9,
        },
        "solution_evidence": {
            "feasibility_status": "not_applicable",
            "solver_converged": True,
            "termination_reason": "deterministic evaluation completed",
            "termination_category": "not_applicable",
            "incumbent_available": False,
            "objective_bound": None,
            "optimality_gap": None,
            "optimality_tolerance": None,
            "optimality_claim": "not_applicable",
            "restart_or_budget_checks": 0,
            "stability_evidence": "deterministic test fixture",
        },
        "limitations": [],
        "error": None,
    }


class ManifestValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.results = self.root / "results"
        self.results.mkdir()
        (self.results / "evidence.txt").write_text("ok", encoding="utf-8")
        (self.results / "ques1.json").write_text(
            json.dumps(valid_contract(), ensure_ascii=False), encoding="utf-8"
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_validator(self, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--results-dir",
                str(self.results),
                "--project-root",
                str(self.root),
                *extra,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def write_manifest(self, contracts: list[dict]) -> None:
        (self.results / "results_contract_manifest.json").write_text(
            json.dumps({"schema_version": "1.0", "contracts": contracts}),
            encoding="utf-8",
        )

    def test_manifest_validates_contract_and_ignores_auxiliary_json(self) -> None:
        self.write_manifest([{"task": "ques1", "file": "ques1.json"}])
        (self.results / "input_inventory.json").write_text("[]", encoding="utf-8")
        completed = self.run_validator()
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("PASS: validated 1 structured result file", completed.stdout)

    def test_missing_manifest_fails_closed(self) -> None:
        completed = self.run_validator()
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("missing results_contract_manifest.json", completed.stdout)

    def test_task_mismatch_is_rejected(self) -> None:
        self.write_manifest([{"task": "ques2", "file": "ques1.json"}])
        completed = self.run_validator()
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("does not match manifest", completed.stdout)

    def test_escape_and_duplicates_are_rejected(self) -> None:
        self.write_manifest(
            [
                {"task": "outside", "file": "../outside.json"},
                {"task": "ques1", "file": "ques1.json"},
                {"task": "ques1", "file": "ques1.json"},
            ]
        )
        completed = self.run_validator()
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("escapes results directory", completed.stdout)
        self.assertIn("duplicates 'ques1'", completed.stdout)

    def overwrite_contract(self, payload: dict) -> None:
        (self.results / "ques1.json").write_text(json.dumps(payload), encoding="utf-8")
        self.write_manifest([{"task": "ques1", "file": "ques1.json"}])

    def test_limit_incumbent_cannot_claim_global(self) -> None:
        payload = valid_contract()
        payload["solution_evidence"].update({
            "feasibility_status": "feasible", "solver_converged": True,
            "termination_category": "limit", "incumbent_available": True,
            "objective_bound": 99.0, "optimality_gap": 0.01,
            "optimality_tolerance": 0.02, "optimality_claim": "global_proven",
        })
        self.overwrite_contract(payload)
        completed = self.run_validator()
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("limit termination cannot claim", completed.stdout)

    def test_nonfinite_gap_is_rejected(self) -> None:
        payload = valid_contract()
        payload["solution_evidence"].update({
            "feasibility_status": "feasible", "termination_category": "normal",
            "incumbent_available": True, "objective_bound": 99.0,
            "optimality_gap": float("inf"), "optimality_tolerance": 0.01,
            "optimality_claim": "global_proven",
        })
        self.overwrite_contract(payload)
        completed = self.run_validator()
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("optimality_gap must be finite", completed.stdout)

    def test_submission_tie_rounding_mismatch_is_rejected(self) -> None:
        payload = valid_contract()
        payload["submission_export"] = {
            "template": "input/template.xlsx", "output": "results/output.xlsx",
            "decimal_places": 3, "rounding_mode": "ROUND_HALF_UP",
            "tie_boundary_test": {"input": 57.5625, "expected": 57.563, "actual": 57.562},
            "export_policy": {"minimum_optimality_claim": "not_applicable", "draft_feasible_only": False},
        }
        self.overwrite_contract(payload)
        completed = self.run_validator()
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("tie boundary actual does not match expected", completed.stdout)

    def test_below_policy_export_requires_draft_label(self) -> None:
        payload = valid_contract()
        payload["solution_evidence"].update({
            "feasibility_status": "feasible", "solver_converged": False,
            "termination_category": "limit", "incumbent_available": True,
            "optimality_claim": "feasible_only",
        })
        payload["submission_export"] = {
            "template": "input/template.xlsx", "output": "results/output.xlsx",
            "decimal_places": 3, "rounding_mode": "ROUND_HALF_UP",
            "tie_boundary_test": {"input": 57.5625, "expected": 57.563, "actual": 57.563},
            "export_policy": {"minimum_optimality_claim": "global_proven", "draft_feasible_only": False},
        }
        self.overwrite_contract(payload)
        completed = self.run_validator()
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("DRAFT_FEASIBLE_ONLY", completed.stdout)

    def test_below_policy_draft_requires_filename_label(self) -> None:
        payload = valid_contract()
        payload["solution_evidence"].update({
            "feasibility_status": "feasible", "solver_converged": False,
            "termination_category": "limit", "incumbent_available": True,
            "optimality_claim": "feasible_only",
        })
        payload["submission_export"] = {
            "template": "input/template.xlsx", "output": "results/output.xlsx",
            "decimal_places": 3, "rounding_mode": "ROUND_HALF_UP",
            "tie_boundary_test": {"input": 57.5625, "expected": 57.563, "actual": 57.563},
            "export_policy": {"minimum_optimality_claim": "global_proven", "draft_feasible_only": True},
        }
        self.overwrite_contract(payload)
        completed = self.run_validator()
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("filename must contain DRAFT_FEASIBLE_ONLY", completed.stdout)


if __name__ == "__main__":
    unittest.main()
