#!/usr/bin/env python3
"""Rebuild declared outputs in an isolated directory from declared source inputs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


FORBIDDEN_INPUT_PARTS = {"results", "figures", "paper", "generated", "reports", "tmp", "cache", "__pycache__"}
WINDOWS_ABSOLUTE = re.compile(r"(?i)(?:^|[\s\"'])(?:[a-z]:[\\/])")


def error(errors: list[str], message: str) -> None:
    errors.append(message)
    print(f"FAIL: {message}")


def safe_relative(root: Path, raw: Any, label: str, errors: list[str]) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        error(errors, f"{label} must be a non-empty relative path")
        return None
    path = Path(raw)
    if path.is_absolute() or WINDOWS_ABSOLUTE.search(raw):
        error(errors, f"{label} must not be absolute: {raw}")
        return None
    resolved = (root / path).resolve()
    try:
        resolved.relative_to(root)
    except ValueError:
        error(errors, f"{label} escapes project root: {raw}")
        return None
    return resolved


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def validate_manifest(payload: Any, root: Path, errors: list[str]) -> tuple[list[Path], list[str], list[str]]:
    if not isinstance(payload, dict):
        error(errors, "reproduction_manifest.json top level must be an object")
        return [], [], []
    if payload.get("schema_version") != "1.0":
        error(errors, "reproduction_manifest.json schema_version must be 1.0")
    raw_inputs = payload.get("copy_inputs")
    commands = payload.get("commands")
    outputs = payload.get("expected_outputs")
    if not isinstance(raw_inputs, list) or not raw_inputs:
        error(errors, "copy_inputs must be a non-empty list")
        raw_inputs = []
    if not isinstance(commands, list) or not commands or not all(isinstance(x, str) and x.strip() for x in commands):
        error(errors, "commands must be a non-empty string list")
        commands = []
    if not isinstance(outputs, list) or not outputs or not all(isinstance(x, str) and x.strip() for x in outputs):
        error(errors, "expected_outputs must be a non-empty string list")
        outputs = []
    inputs: list[Path] = []
    for index, raw in enumerate(raw_inputs):
        path = safe_relative(root, raw, f"copy_inputs[{index}]", errors)
        if path is None:
            continue
        relative = path.relative_to(root)
        if any(part.lower() in FORBIDDEN_INPUT_PARTS for part in relative.parts):
            error(errors, f"copy_inputs[{index}] includes generated state: {raw}")
            continue
        if not path.exists():
            error(errors, f"copy_inputs[{index}] does not exist: {raw}")
            continue
        inputs.append(path)
    root_text = str(root.resolve()).replace("/", "\\").lower()
    for index, command in enumerate(commands):
        normalized = command.replace("/", "\\").lower()
        if WINDOWS_ABSOLUTE.search(command) or root_text in normalized:
            error(errors, f"commands[{index}] contains an absolute path")
    for index, raw in enumerate(outputs):
        safe_relative(root, raw, f"expected_outputs[{index}]", errors)
    return inputs, list(commands), list(outputs)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", required=True, type=Path)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--keep-temp", action="store_true")
    parser.add_argument("--timeout", type=int, default=3600)
    args = parser.parse_args()
    root = args.project_root.resolve()
    manifest = (args.manifest or (root / "reproduction_manifest.json")).resolve()
    errors: list[str] = []
    if not manifest.is_file():
        error(errors, f"missing reproduction manifest: {manifest}")
        return 1
    try:
        payload = json.loads(manifest.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - report malformed manifest
        error(errors, f"invalid reproduction manifest JSON: {exc}")
        return 1
    inputs, commands, outputs = validate_manifest(payload, root, errors)
    if errors:
        return 1
    temp_root = Path(tempfile.mkdtemp(prefix="mathmodel-clean-replay-"))
    replay = temp_root / "project"
    replay.mkdir()
    try:
        for source in inputs:
            relative = source.relative_to(root)
            target = replay / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if source.is_dir():
                shutil.copytree(source, target, dirs_exist_ok=True)
            else:
                shutil.copy2(source, target)
        env = os.environ.copy()
        env.setdefault("MPLBACKEND", "Agg")
        for index, command in enumerate(commands):
            completed = subprocess.run(
                command,
                cwd=replay,
                env=env,
                shell=True,
                capture_output=True,
                text=True,
                timeout=args.timeout,
            )
            print(f"COMMAND {index + 1}: exit={completed.returncode} {command}")
            if completed.returncode:
                if completed.stdout:
                    print(completed.stdout[-4000:])
                if completed.stderr:
                    print(completed.stderr[-4000:], file=sys.stderr)
                error(errors, f"commands[{index}] failed with exit {completed.returncode}")
                break
        hashes: dict[str, str] = {}
        if not errors:
            for index, raw in enumerate(outputs):
                target = safe_relative(replay, raw, f"expected_outputs[{index}]", errors)
                if target is None:
                    continue
                if not target.is_file():
                    error(errors, f"expected output missing after clean replay: {raw}")
                else:
                    hashes[raw] = sha256(target)
        if errors:
            return 1
        print(json.dumps({"status": "PASS", "temporary_root": str(replay), "output_sha256": hashes}, indent=2))
        return 0
    finally:
        if args.keep_temp:
            print(f"TEMP_RETAINED: {temp_root}")
        else:
            shutil.rmtree(temp_root, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
