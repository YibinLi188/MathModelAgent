#!/usr/bin/env python3
"""Validate per-question structured result contracts without project dependencies."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


RESERVED = {"raw_results.json", "all_results.json", "run_manifest.json"}


def fail(errors: list[str], message: str) -> None:
    errors.append(message)
    print(f"FAIL: {message}")


def require(mapping: dict[str, Any], key: str, errors: list[str], path: Path) -> Any:
    if key not in mapping:
        fail(errors, f"{path.name}: missing {key}")
        return None
    return mapping[key]


def validate(path: Path, root: Path, errors: list[str]) -> None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - report malformed result files
        fail(errors, f"{path.name}: invalid JSON ({exc})")
        return
    if not isinstance(payload, dict):
        fail(errors, f"{path.name}: top level must be an object")
        return
    if require(payload, "schema_version", errors, path) != "1.0":
        fail(errors, f"{path.name}: schema_version must be 1.0")
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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results-dir", required=True, type=Path)
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument("--expected-tasks", default="", help="comma-separated task ids, e.g. ques1,ques2")
    args = parser.parse_args()
    results_dir = args.results_dir.resolve()
    root = (args.project_root or results_dir.parent).resolve()
    errors: list[str] = []
    if not results_dir.is_dir():
        print(f"FAIL: results directory does not exist: {results_dir}")
        return 1
    files = [p for p in sorted(results_dir.glob("*.json")) if p.name not in RESERVED]
    expected = [x.strip() for x in args.expected_tasks.split(",") if x.strip()]
    if expected:
        by_task = {p.stem: p for p in files}
        for task in expected:
            path = by_task.get(task)
            if path is None:
                fail(errors, f"missing result file for expected task {task}")
            else:
                validate(path, root, errors)
    else:
        if not files:
            fail(errors, "no per-question JSON files found")
        for path in files:
            validate(path, root, errors)
    if errors:
        print(f"{len(errors)} contract error(s)")
        return 1
    print(f"PASS: validated {len(expected) if expected else len(files)} structured result file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
