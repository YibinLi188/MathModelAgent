#!/usr/bin/env python3
"""Regression tests for isolated replay manifests."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("validate_clean_replay.py")


class CleanReplayTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "input").mkdir()
        (self.root / "code").mkdir()
        (self.root / "input" / "value.txt").write_text("41", encoding="utf-8")
        (self.root / "code" / "build.py").write_text(
            "from pathlib import Path\n"
            "root=Path(__file__).resolve().parents[1]\n"
            "(root/'results').mkdir(exist_ok=True)\n"
            "v=int((root/'input/value.txt').read_text())+1\n"
            "(root/'results/answer.txt').write_text(str(v))\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def run_validator(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), "--project-root", str(self.root), "--timeout", "30"],
            check=False,
            capture_output=True,
            text=True,
        )

    def write_manifest(self, payload: dict) -> None:
        (self.root / "reproduction_manifest.json").write_text(json.dumps(payload), encoding="utf-8")

    def test_clean_replay_passes(self) -> None:
        self.write_manifest({
            "schema_version": "1.0",
            "copy_inputs": ["input", "code"],
            "commands": ["python code/build.py"],
            "expected_outputs": ["results/answer.txt"],
        })
        completed = self.run_validator()
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn('"status": "PASS"', completed.stdout)

    def test_generated_input_is_rejected(self) -> None:
        (self.root / "results").mkdir()
        self.write_manifest({
            "schema_version": "1.0",
            "copy_inputs": ["input", "results"],
            "commands": ["python code/build.py"],
            "expected_outputs": ["results/answer.txt"],
        })
        completed = self.run_validator()
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("includes generated state", completed.stdout)

    def test_absolute_command_is_rejected(self) -> None:
        self.write_manifest({
            "schema_version": "1.0",
            "copy_inputs": ["input", "code"],
            "commands": [r"python D:\\old-work\\build.py"],
            "expected_outputs": ["results/answer.txt"],
        })
        completed = self.run_validator()
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("contains an absolute path", completed.stdout)

    def test_missing_output_is_rejected(self) -> None:
        self.write_manifest({
            "schema_version": "1.0",
            "copy_inputs": ["input", "code"],
            "commands": ["python code/build.py"],
            "expected_outputs": ["results/missing.txt"],
        })
        completed = self.run_validator()
        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("expected output missing", completed.stdout)


if __name__ == "__main__":
    unittest.main()
