#!/usr/bin/env python3
"""Validate per-question structured result contracts without project dependencies."""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Any


DEFAULT_MANIFEST = "results_contract_manifest.json"
VALID_FEASIBILITY = {"feasible", "infeasible", "not_applicable"}
VALID_OPTIMALITY = {"global_proven", "local_converged", "feasible_only", "not_applicable"}
VALID_COMBINATION_SCOPE = {"observed_combinations_only", "interpolated_design_space", "extrapolated_candidate_space"}
VALID_POINT_ROLES = {"feasible_candidate", "supremum_reference", "infeasible_reference"}
VALID_TERMINATION = {"normal", "limit", "interrupted", "numerical", "infeasible", "not_applicable"}
CLAIM_LEVEL = {"not_applicable": 0, "feasible_only": 1, "local_converged": 2, "global_proven": 3}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)
    print(f"FAIL: {message}")


def require(mapping: dict[str, Any], key: str, errors: list[str], path: Path) -> Any:
    if key not in mapping:
        fail(errors, f"{path.name}: missing {key}")
        return None
    return mapping[key]


def validate_resource(resource: Any, errors: list[str], path: Path) -> None:
    """Check the portable, machine-readable resource comparison contract."""
    if not isinstance(resource, dict):
        fail(errors, f"{path.name}: resource must be an object")
        return
    if resource.get("status") != "resource_passed":
        fail(errors, f"{path.name}: resource.status must be resource_passed")
    rule = resource.get("decision_rule")
    if rule not in {"strict_improvement", "pareto_tradeoff"}:
        fail(errors, f"{path.name}: invalid resource.decision_rule")
    quality = resource.get("quality_constraints")
    if not isinstance(quality, dict) or not quality:
        fail(errors, f"{path.name}: resource.quality_constraints must be a non-empty object")
    elif not all(value is True for value in quality.values()):
        fail(errors, f"{path.name}: every resource quality constraint must be true")
    parties: dict[str, dict[str, Any]] = {}
    for name in ("baseline", "candidate"):
        party = resource.get(name)
        if not isinstance(party, dict):
            fail(errors, f"{path.name}: resource.{name} must be an object")
            continue
        parties[name] = party
        for key in ("id", "run_command", "metrics"):
            if key not in party:
                fail(errors, f"{path.name}: resource.{name} missing {key}")
        metrics = party.get("metrics")
        if not isinstance(metrics, dict) or not metrics:
            fail(errors, f"{path.name}: resource.{name}.metrics must be a non-empty object")
            continue
        for metric_name, metric in metrics.items():
            if not isinstance(metric, dict):
                fail(errors, f"{path.name}: resource.{name}.{metric_name} must be an object")
                continue
            if not isinstance(metric.get("value"), (int, float)):
                fail(errors, f"{path.name}: resource.{name}.{metric_name}.value must be numeric")
            if not isinstance(metric.get("unit"), str) or not metric["unit"].strip():
                fail(errors, f"{path.name}: resource.{name}.{metric_name}.unit must be non-empty")
            if metric.get("direction") not in {"min", "max"}:
                fail(errors, f"{path.name}: resource.{name}.{metric_name}.direction must be min or max")
    comparison = resource.get("comparison")
    if not isinstance(comparison, dict):
        fail(errors, f"{path.name}: resource.comparison must be an object")
        return
    improvements = comparison.get("strict_improvements")
    if not isinstance(improvements, list) or not improvements or not all(isinstance(x, str) and x for x in improvements):
        fail(errors, f"{path.name}: resource.comparison.strict_improvements must be a non-empty string list")
    elif len(parties) == 2:
        baseline = parties["baseline"].get("metrics", {})
        candidate = parties["candidate"].get("metrics", {})
        for name in improvements:
            left, right = baseline.get(name), candidate.get(name)
            if not isinstance(left, dict) or not isinstance(right, dict):
                fail(errors, f"{path.name}: resource improvement {name} missing from baseline or candidate")
                continue
            if left.get("unit") != right.get("unit") or left.get("direction") != right.get("direction"):
                fail(errors, f"{path.name}: resource improvement {name} changes unit or direction")
                continue
            if not isinstance(left.get("value"), (int, float)) or not isinstance(right.get("value"), (int, float)):
                continue
            if left["direction"] == "min" and not right["value"] < left["value"]:
                fail(errors, f"{path.name}: resource improvement {name} is not strictly lower")
            if left["direction"] == "max" and not right["value"] > left["value"]:
                fail(errors, f"{path.name}: resource improvement {name} is not strictly higher")
    tradeoffs = comparison.get("accepted_tradeoffs")
    if not isinstance(tradeoffs, list):
        fail(errors, f"{path.name}: resource.comparison.accepted_tradeoffs must be a list")
    if rule == "strict_improvement" and tradeoffs:
        fail(errors, f"{path.name}: strict_improvement cannot contain accepted tradeoffs")
    if rule == "pareto_tradeoff":
        if not tradeoffs:
            fail(errors, f"{path.name}: pareto_tradeoff requires at least one explicit tradeoff")
        for item in tradeoffs:
            if not isinstance(item, dict) or not all(isinstance(item.get(key), str) and item[key].strip() for key in ("metric", "reason", "boundary")):
                fail(errors, f"{path.name}: each accepted tradeoff needs metric, reason, and boundary")
    if not isinstance(comparison.get("worst_case_scope"), str) or not comparison["worst_case_scope"].strip():
        fail(errors, f"{path.name}: resource.comparison.worst_case_scope must be non-empty")


def validate_solution_evidence(evidence: Any, errors: list[str], path: Path) -> None:
    """Keep execution success separate from feasibility, convergence, and optimality."""
    if not isinstance(evidence, dict):
        fail(errors, f"{path.name}: solution_evidence must be an object")
        return
    feasibility = evidence.get("feasibility_status")
    converged = evidence.get("solver_converged")
    reason = evidence.get("termination_reason")
    claim = evidence.get("optimality_claim")
    checks = evidence.get("restart_or_budget_checks")
    stability = evidence.get("stability_evidence")
    category = evidence.get("termination_category")
    incumbent = evidence.get("incumbent_available")
    bound = evidence.get("objective_bound")
    gap = evidence.get("optimality_gap")
    tolerance = evidence.get("optimality_tolerance")
    if feasibility not in VALID_FEASIBILITY:
        fail(errors, f"{path.name}: invalid solution_evidence.feasibility_status")
    if not isinstance(converged, bool):
        fail(errors, f"{path.name}: solution_evidence.solver_converged must be boolean")
    if not isinstance(reason, str) or not reason.strip():
        fail(errors, f"{path.name}: solution_evidence.termination_reason must be non-empty")
    if claim not in VALID_OPTIMALITY:
        fail(errors, f"{path.name}: invalid solution_evidence.optimality_claim")
    if not isinstance(checks, int) or isinstance(checks, bool) or checks < 0:
        fail(errors, f"{path.name}: solution_evidence.restart_or_budget_checks must be a non-negative integer")
    if not isinstance(stability, str) or not stability.strip():
        fail(errors, f"{path.name}: solution_evidence.stability_evidence must be non-empty")
    if category not in VALID_TERMINATION:
        fail(errors, f"{path.name}: invalid solution_evidence.termination_category")
    if not isinstance(incumbent, bool):
        fail(errors, f"{path.name}: solution_evidence.incumbent_available must be boolean")
    for key, value in (("objective_bound", bound), ("optimality_gap", gap), ("optimality_tolerance", tolerance)):
        if value is not None and (not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value)):
            fail(errors, f"{path.name}: solution_evidence.{key} must be finite numeric or null")
    if converged is False and claim not in {"feasible_only", "not_applicable"}:
        fail(errors, f"{path.name}: non-converged solver cannot claim {claim!r}")
    if claim in {"local_converged", "global_proven"} and converged is not True:
        fail(errors, f"{path.name}: {claim} requires solver_converged=true")
    if claim == "feasible_only" and feasibility != "feasible":
        fail(errors, f"{path.name}: feasible_only requires feasibility_status=feasible")
    if category in {"limit", "interrupted", "numerical"} and converged is not False:
        fail(errors, f"{path.name}: termination_category={category} requires solver_converged=false")
    if category == "limit" and claim not in {"feasible_only", "not_applicable"}:
        fail(errors, f"{path.name}: limit termination cannot claim {claim!r}")
    if claim == "feasible_only" and incumbent is not True:
        fail(errors, f"{path.name}: feasible_only requires incumbent_available=true")
    if claim == "global_proven":
        if category != "normal":
            fail(errors, f"{path.name}: global_proven requires normal termination")
        if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) for value in (bound, gap, tolerance)):
            fail(errors, f"{path.name}: global_proven requires finite bound, gap, and tolerance")
        elif gap < 0 or tolerance < 0 or gap > tolerance:
            fail(errors, f"{path.name}: global_proven gap exceeds tolerance")


def validate_submission_export(export: Any, evidence: Any, errors: list[str], path: Path) -> None:
    """Validate official-template rounding and claim-aware export policy."""
    if not isinstance(export, dict):
        fail(errors, f"{path.name}: submission_export must be an object")
        return
    for key in ("template", "output"):
        if not isinstance(export.get(key), str) or not export[key].strip():
            fail(errors, f"{path.name}: submission_export.{key} must be non-empty")
    decimals = export.get("decimal_places")
    if not isinstance(decimals, int) or isinstance(decimals, bool) or decimals < 0:
        fail(errors, f"{path.name}: submission_export.decimal_places must be a non-negative integer")
    if export.get("rounding_mode") not in {"ROUND_HALF_UP", "ROUND_HALF_EVEN", "ROUND_DOWN", "ROUND_UP"}:
        fail(errors, f"{path.name}: submission_export.rounding_mode is invalid")
    boundary = export.get("tie_boundary_test")
    if not isinstance(boundary, dict):
        fail(errors, f"{path.name}: submission_export.tie_boundary_test must be an object")
    else:
        values = [boundary.get(key) for key in ("input", "expected", "actual")]
        if not all(isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) for value in values):
            fail(errors, f"{path.name}: tie boundary input/expected/actual must be finite numeric")
        elif abs(values[1] - values[2]) > 10 ** (-(decimals if isinstance(decimals, int) else 0)) / 10:
            fail(errors, f"{path.name}: tie boundary actual does not match expected")
    policy = export.get("export_policy")
    if not isinstance(policy, dict):
        fail(errors, f"{path.name}: submission_export.export_policy must be an object")
        return
    minimum = policy.get("minimum_optimality_claim")
    draft = policy.get("draft_feasible_only")
    if minimum not in CLAIM_LEVEL:
        fail(errors, f"{path.name}: invalid minimum_optimality_claim")
        return
    if not isinstance(draft, bool):
        fail(errors, f"{path.name}: draft_feasible_only must be boolean")
        return
    claim = evidence.get("optimality_claim") if isinstance(evidence, dict) else None
    if claim in CLAIM_LEVEL and CLAIM_LEVEL[claim] < CLAIM_LEVEL[minimum]:
        if draft is not True:
            fail(errors, f"{path.name}: export below policy must be marked DRAFT_FEASIBLE_ONLY")
        elif "DRAFT_FEASIBLE_ONLY" not in export.get("output", ""):
            fail(errors, f"{path.name}: draft output filename must contain DRAFT_FEASIBLE_ONLY")


def validate_comparison_semantics(semantics: Any, errors: list[str], path: Path) -> None:
    """Validate the definition needed before comparing results across model conventions."""
    if not isinstance(semantics, dict):
        fail(errors, f"{path.name}: comparison_semantics must be an object")
        return
    required = (
        "surface_or_entity_model",
        "numerator",
        "denominator",
        "weighting",
        "sampling_unit",
        "boundary_rule",
        "uncertainty",
    )
    for key in required:
        value = semantics.get(key)
        if not isinstance(value, str) or not value.strip():
            fail(errors, f"{path.name}: comparison_semantics.{key} must be non-empty")
    refs = semantics.get("comparable_reference_ids")
    if not isinstance(refs, list) or not all(isinstance(item, str) and item.strip() for item in refs):
        fail(errors, f"{path.name}: comparison_semantics.comparable_reference_ids must be a string list")


def validate_optimization_domain(domain: Any, errors: list[str], path: Path) -> None:
    """Make optimization scope, open bounds, and grouped validation auditable."""
    if not isinstance(domain, dict):
        fail(errors, f"{path.name}: optimization_domain must be an object")
        return
    variables = domain.get("decision_variables")
    numeric_variables: dict[str, dict[str, Any]] = {}
    if not isinstance(variables, list) or not variables:
        fail(errors, f"{path.name}: optimization_domain.decision_variables must be non-empty")
    else:
        for index, variable in enumerate(variables):
            prefix = f"{path.name}: decision_variables[{index}]"
            if not isinstance(variable, dict):
                fail(errors, f"{prefix} must be an object")
                continue
            if not isinstance(variable.get("name"), str) or not variable["name"].strip():
                fail(errors, f"{prefix}.name must be non-empty")
            if variable.get("type") not in {"continuous", "integer", "categorical"}:
                fail(errors, f"{prefix}.type is invalid")
            if variable.get("type") != "categorical":
                if isinstance(variable.get("name"), str):
                    numeric_variables[variable["name"]] = variable
                for key in ("lower", "upper"):
                    if not isinstance(variable.get(key), (int, float)):
                        fail(errors, f"{prefix}.{key} must be numeric")
                for key in ("lower_exclusive", "upper_exclusive"):
                    if not isinstance(variable.get(key), bool):
                        fail(errors, f"{prefix}.{key} must be boolean")
    if domain.get("combination_scope") not in VALID_COMBINATION_SCOPE:
        fail(errors, f"{path.name}: invalid optimization_domain.combination_scope")
    for key in ("interpolation", "extrapolation", "boundary_interpretation"):
        if not isinstance(domain.get(key), str) or not domain[key].strip():
            fail(errors, f"{path.name}: optimization_domain.{key} must be non-empty")
    safety = domain.get("safety_constraints")
    if not isinstance(safety, list) or not all(isinstance(x, str) and x.strip() for x in safety):
        fail(errors, f"{path.name}: optimization_domain.safety_constraints must be a string list")
    split = domain.get("validation_split")
    if not isinstance(split, dict):
        fail(errors, f"{path.name}: optimization_domain.validation_split must be an object")
    else:
        if not isinstance(split.get("group_key"), str) or not split["group_key"].strip():
            fail(errors, f"{path.name}: validation_split.group_key must be non-empty")
        if split.get("overlap_count") != 0:
            fail(errors, f"{path.name}: validation_split.overlap_count must be 0")
    points = domain.get("reported_points")
    if not isinstance(points, list) or not points:
        fail(errors, f"{path.name}: optimization_domain.reported_points must be non-empty")
    else:
        for index, point in enumerate(points):
            prefix = f"{path.name}: reported_points[{index}]"
            if not isinstance(point, dict):
                fail(errors, f"{prefix} must be an object")
                continue
            if not isinstance(point.get("label"), str) or not point["label"].strip():
                fail(errors, f"{prefix}.label must be non-empty")
            role = point.get("role")
            if role not in VALID_POINT_ROLES:
                fail(errors, f"{prefix}.role is invalid")
            values = point.get("values")
            if not isinstance(values, dict) or not values:
                fail(errors, f"{prefix}.values must be a non-empty object")
                continue
            if role != "feasible_candidate":
                continue
            for name, variable in numeric_variables.items():
                if name not in values:
                    continue
                value = values[name]
                if not isinstance(value, (int, float)):
                    fail(errors, f"{prefix}.values.{name} must be numeric")
                    continue
                lower, upper = variable.get("lower"), variable.get("upper")
                if isinstance(lower, (int, float)):
                    outside = value <= lower if variable.get("lower_exclusive") else value < lower
                    if outside:
                        fail(errors, f"{prefix}.values.{name} violates lower bound")
                if isinstance(upper, (int, float)):
                    outside = value >= upper if variable.get("upper_exclusive") else value > upper
                    if outside:
                        fail(errors, f"{prefix}.values.{name} violates upper bound")


def validate(path: Path, root: Path, errors: list[str], require_resource: bool) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - report malformed result files
        fail(errors, f"{path.name}: invalid JSON ({exc})")
        return
    if not isinstance(payload, dict):
        fail(errors, f"{path.name}: top level must be an object")
        return
    if require(payload, "schema_version", errors, path) != "1.2":
        fail(errors, f"{path.name}: schema_version must be 1.2")
    status = require(payload, "status", errors, path)
    if status != "success":
        fail(errors, f"{path.name}: status must be success (got {status!r})")
    require(payload, "task", errors, path)
    hashes = require(payload, "data_hashes", errors, path)
    if not isinstance(hashes, list) or not hashes or not all(isinstance(x, str) and x.strip() for x in hashes):
        fail(errors, f"{path.name}: data_hashes must be a non-empty list")
    sample = require(payload, "sample", errors, path)
    if not isinstance(sample, dict) or not sample:
        fail(errors, f"{path.name}: sample must be a non-empty object")
    metrics = require(payload, "metrics", errors, path)
    semantics = require(payload, "metric_semantics", errors, path)
    if not isinstance(metrics, dict) or not metrics:
        fail(errors, f"{path.name}: metrics must be a non-empty object")
    if not isinstance(semantics, dict) or not semantics:
        fail(errors, f"{path.name}: metric_semantics must be a non-empty object")
    elif isinstance(metrics, dict):
        missing_semantics = sorted(set(metrics) - set(semantics))
        if missing_semantics:
            fail(errors, f"{path.name}: missing metric semantics for {missing_semantics}")
    require(payload, "parameters", errors, path)
    artifacts = require(payload, "artifacts", errors, path)
    if not isinstance(artifacts, list) or not artifacts:
        fail(errors, f"{path.name}: artifacts must be a non-empty list")
    else:
        for item in artifacts:
            if not isinstance(item, str) or not item.strip():
                fail(errors, f"{path.name}: artifact path must be a non-empty string")
                continue
            artifact = (root / item).resolve()
            try:
                artifact.relative_to(root.resolve())
            except ValueError:
                fail(errors, f"{path.name}: artifact escapes project root: {item}")
                continue
            if not artifact.is_file():
                fail(errors, f"{path.name}: missing artifact: {item}")
    validation = require(payload, "validation", errors, path)
    if not isinstance(validation, dict):
        fail(errors, f"{path.name}: validation must be an object")
    else:
        if validation.get("independent_recompute") is not True:
            fail(errors, f"{path.name}: independent_recompute must be true")
        for key in ("independent_delta", "tolerance"):
            value = validation.get(key)
            if not isinstance(value, (int, float)):
                fail(errors, f"{path.name}: validation.{key} must be numeric")
    limitations = require(payload, "limitations", errors, path)
    if not isinstance(limitations, list):
        fail(errors, f"{path.name}: limitations must be a list")
    if "error" not in payload:
        fail(errors, f"{path.name}: missing error field")
    elif status == "success" and payload["error"] is not None:
        fail(errors, f"{path.name}: successful result must have error=null")
    evidence = require(payload, "solution_evidence", errors, path)
    validate_solution_evidence(evidence, errors, path)
    if "submission_export" in payload:
        validate_submission_export(payload["submission_export"], evidence, errors, path)
    if "comparison_semantics" in payload:
        validate_comparison_semantics(payload["comparison_semantics"], errors, path)
    if "optimization_domain" in payload:
        validate_optimization_domain(payload["optimization_domain"], errors, path)
    elif isinstance(evidence, dict) and evidence.get("optimality_claim") != "not_applicable":
        fail(errors, f"{path.name}: optimization result missing optimization_domain")
    if require_resource:
        if "resource" not in payload:
            fail(errors, f"{path.name}: missing resource contract")
        else:
            validate_resource(payload["resource"], errors, path)


def load_manifest(path: Path, results_dir: Path, errors: list[str]) -> list[tuple[str, Path]]:
    """Resolve explicit question contracts without treating audit JSON as contracts."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - report malformed manifests
        fail(errors, f"{path.name}: invalid JSON ({exc})")
        return []
    if not isinstance(payload, dict):
        fail(errors, f"{path.name}: top level must be an object")
        return []
    if payload.get("schema_version") != "1.0":
        fail(errors, f"{path.name}: schema_version must be 1.0")
    contracts = payload.get("contracts")
    if not isinstance(contracts, list) or not contracts:
        fail(errors, f"{path.name}: contracts must be a non-empty list")
        return []
    resolved: list[tuple[str, Path]] = []
    seen_tasks: set[str] = set()
    seen_paths: set[Path] = set()
    for index, item in enumerate(contracts):
        prefix = f"{path.name}: contracts[{index}]"
        if not isinstance(item, dict):
            fail(errors, f"{prefix} must be an object")
            continue
        task = item.get("task")
        relative = item.get("file")
        if not isinstance(task, str) or not task.strip():
            fail(errors, f"{prefix}.task must be non-empty")
            continue
        if not isinstance(relative, str) or not relative.strip():
            fail(errors, f"{prefix}.file must be non-empty")
            continue
        candidate = (results_dir / relative).resolve()
        try:
            candidate.relative_to(results_dir)
        except ValueError:
            fail(errors, f"{prefix}.file escapes results directory: {relative}")
            continue
        if candidate.suffix.lower() != ".json":
            fail(errors, f"{prefix}.file must name a JSON file")
            continue
        if task in seen_tasks:
            fail(errors, f"{prefix}.task duplicates {task!r}")
            continue
        if candidate in seen_paths:
            fail(errors, f"{prefix}.file duplicates {relative!r}")
            continue
        seen_tasks.add(task)
        seen_paths.add(candidate)
        if not candidate.is_file():
            fail(errors, f"{prefix}.file does not exist: {relative}")
            continue
        try:
            contract = json.loads(candidate.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001 - validate reports the contract later
            fail(errors, f"{candidate.name}: invalid JSON ({exc})")
            continue
        actual_task = contract.get("task") if isinstance(contract, dict) else None
        if actual_task != task:
            fail(errors, f"{candidate.name}: task {actual_task!r} does not match manifest {task!r}")
            continue
        resolved.append((task, candidate))
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", required=True, type=Path)
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument("--expected-tasks", default="", help="comma-separated task ids, e.g. ques1,ques2")
    parser.add_argument("--manifest", type=Path, default=None, help=f"explicit contract manifest; defaults to results-dir/{DEFAULT_MANIFEST}")
    parser.add_argument("--scan-all", action="store_true", help="legacy diagnostic: validate every JSON except the contract manifest")
    parser.add_argument("--require-resource", action="store_true", help="require and validate a resource comparison object for every checked task")
    args = parser.parse_args()
    results_dir = args.results_dir.resolve()
    root = (args.project_root or results_dir.parent).resolve()
    errors: list[str] = []
    if not results_dir.is_dir():
        print(f"FAIL: results directory does not exist: {results_dir}")
        return 1
    expected = [x.strip() for x in args.expected_tasks.split(",") if x.strip()]
    if expected:
        files = [p for p in sorted(results_dir.glob("*.json")) if p.name != DEFAULT_MANIFEST]
        by_task = {p.stem: p for p in files}
        for task in expected:
            path = by_task.get(task)
            if path is None:
                fail(errors, f"missing result file for expected task {task}")
            else:
                validate(path, root, errors, args.require_resource)
    else:
        manifest = (args.manifest or (results_dir / DEFAULT_MANIFEST)).resolve()
        if manifest.is_file():
            entries = load_manifest(manifest, results_dir, errors)
            for _, path in entries:
                validate(path, root, errors, args.require_resource)
            expected = [task for task, _ in entries]
        elif args.scan_all:
            files = [p for p in sorted(results_dir.glob("*.json")) if p.name != DEFAULT_MANIFEST]
            if not files:
                fail(errors, "no JSON files found")
            for path in files:
                validate(path, root, errors, args.require_resource)
        else:
            fail(errors, f"missing {DEFAULT_MANIFEST}; provide --expected-tasks or use --scan-all explicitly")
    if errors:
        print(f"{len(errors)} contract error(s)")
        return 1
    print(f"PASS: validated {len(expected) if expected else len(files)} structured result file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
