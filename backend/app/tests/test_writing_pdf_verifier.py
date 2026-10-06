"""Regression tests for the LaTeX/PDF writing-skill verifier."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import fitz
import pytest


REPO_ROOT = Path(__file__).resolve().parents[3]
VERIFIER_PATH = REPO_ROOT / "skills" / "5writing" / "scripts" / "verify_latex_pdf.py"
SPEC = importlib.util.spec_from_file_location("writing_pdf_verifier", VERIFIER_PATH)
assert SPEC and SPEC.loader
VERIFIER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VERIFIER)


def test_source_gate_scans_included_tex_files(tmp_path: Path) -> None:
    (tmp_path / "sections").mkdir()
    (tmp_path / "main.tex").write_text(
        r"\documentclass{ctexart}\begin{document}\input{sections/body}\end{document}",
        encoding="utf-8",
    )
    (tmp_path / "sections" / "body.tex").write_text(
        "验收时间：2026-10-06", encoding="utf-8"
    )

    with pytest.raises(RuntimeError, match="source hard gate failed"):
        VERIFIER.inspect_source(tmp_path)


def _write_benchmark_fixture(path: Path) -> None:
    document = fitz.open()
    for page_index in range(3):
        page = document.new_page(width=595.28, height=841.89)
        page.insert_text((72, 90), "数学建模正文", fontname="china-s", fontsize=12)
        page.insert_text((72, 700), "数值验证结论", fontname="china-s", fontsize=12)
        if page_index == 2:
            page.insert_text((230, 400), "参考文献", fontname="china-s", fontsize=16)
    document.save(path)


def test_pdf_gate_uses_benchmark_main_page_floor(tmp_path: Path) -> None:
    pdf_path = tmp_path / "main.pdf"
    _write_benchmark_fixture(pdf_path)

    result = VERIFIER.inspect_pdf(pdf_path, None, minimum_main_pages=3)
    assert result["reference_start_page"] == 3
    assert result["main_text_pages"] == 3

    with pytest.raises(RuntimeError, match="shorter than benchmark floor"):
        VERIFIER.inspect_pdf(pdf_path, None, minimum_main_pages=4)
