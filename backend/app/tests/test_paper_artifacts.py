from __future__ import annotations

import json
import shutil
import zipfile
from pathlib import Path

import fitz
import pytest

from app.models.user_output import UserOutput
from app.schemas.enums import FormatOutPut
from app.services import paper_artifacts
from app.tools.base_interpreter import BaseCodeInterpreter
from app.services.paper_artifacts import (
    PaperArtifactError,
    _compile_latex,
    _inspect_pdf,
    _validate_compile_log,
    prepare_latex_source,
)


def _sections(question_count: int = 2) -> dict[str, str]:
    sections = {
        "firstPage": (
            "<PAPER_TITLE>测试论文标题</PAPER_TITLE>\n"
            "<PAPER_ABSTRACT>本文研究测试问题。问题一采用线性模型并得到数值结果；"
            "问题二通过扰动检验验证稳定性。</PAPER_ABSTRACT>\n"
            "<PAPER_KEYWORDS>线性模型，稳定性，数值验证，数学建模</PAPER_KEYWORDS>"
        ),
        "RepeatQues": "\\section{问题重述}\n这里是问题重述。",
        "analysisQues": "\\section{问题分析}\n这里是问题分析。",
        "modelAssumption": "\\section{模型假设}\n这里是模型假设。",
        "symbol": "\\section{符号说明}\n这里是符号说明。",
        "eda": "\\section{数据预处理}\n这里是数据预处理。",
    }
    for index in range(1, question_count + 1):
        sections[f"ques{index}"] = (
            f"\\section{{问题{index}模型的建立与求解}}\n"
            f"问题{index}给出模型、结果和验证。"
        )
    sections["sensitivity_analysis"] = "\\section{模型检验}\n扰动检验通过。"
    sections["judge"] = "\\section{模型评价}\n说明局限与适用范围。"
    return sections


def test_prepare_latex_source_uses_dynamic_questions_and_one_bibliography(tmp_path: Path):
    main_tex = prepare_latex_source(
        tmp_path,
        _sections(question_count=4),
        ["张三. 示例文献[J]. 测试期刊, 2024."],
    )
    text = main_tex.read_text(encoding="utf-8")
    assert "问题4模型的建立与求解" in text
    assert text.count("\\section*{参考文献}") == 1
    assert text.count("\\bibitem{ref1}") == 1
    assert "fontset=none" in text
    assert "Noto Serif CJK SC" in text
    assert "textcolor" not in text
    assert "生成时间" not in text


def test_prepare_latex_source_converts_referenced_svg_to_pdf(tmp_path: Path):
    (tmp_path / "chart.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="100" height="40">'
        '<rect width="100" height="40" fill="white"/>'
        '<path d="M5 35 L50 5 L95 25" stroke="black" fill="none"/>'
        "</svg>",
        encoding="utf-8",
    )
    sections = _sections()
    sections["analysisQues"] += r"\includegraphics[width=.5\textwidth]{chart.svg}"
    main_tex = prepare_latex_source(tmp_path, sections, [])
    text = main_tex.read_text(encoding="utf-8")
    assert r"\includegraphics[width=.5\textwidth]{figures/chart.pdf}" in text
    assert (tmp_path / "paper" / "figures" / "chart.pdf").is_file()


@pytest.mark.parametrize(
    "bad_fragment",
    [
        r"\section{问题分析}\newpage 非法分页",
        r"\section{\textcolor{blue}{问题分析}} 非法颜色",
        "# 问题分析\n混入 Markdown",
    ],
)
def test_prepare_latex_source_rejects_writer_owned_layout(
    tmp_path: Path, bad_fragment: str
):
    sections = _sections()
    sections["analysisQues"] = bad_fragment
    with pytest.raises(PaperArtifactError):
        prepare_latex_source(tmp_path, sections, [])


def test_prepare_latex_source_rejects_generation_metadata(tmp_path: Path):
    sections = _sections()
    sections["firstPage"] = sections["firstPage"].replace(
        "测试论文标题", "测试论文标题 论文生成时间：2026-08-23"
    )
    with pytest.raises(PaperArtifactError):
        prepare_latex_source(tmp_path, sections, [])


def test_prepare_latex_source_rejects_text_outside_front_matter(tmp_path: Path):
    sections = _sections()
    sections["firstPage"] += "\n以下是生成验收说明"
    with pytest.raises(PaperArtifactError, match="标签外"):
        prepare_latex_source(tmp_path, sections, [])


def test_user_output_keeps_markdown_and_latex_paths_separate(tmp_path: Path):
    markdown_dir = tmp_path / "markdown"
    latex_dir = tmp_path / "latex"
    markdown_dir.mkdir()
    latex_dir.mkdir()

    markdown = UserOutput(str(markdown_dir), ques_count=1)
    latex = UserOutput(str(latex_dir), ques_count=1)
    for output in (markdown, latex):
        for key, value in _sections(question_count=1).items():
            output.res[key] = {"response_content": value, "footnotes": []}

    markdown.save_result(FormatOutPut.Markdown)
    latex.save_result(FormatOutPut.LaTeX)

    assert (markdown_dir / "res.md").is_file()
    assert not (markdown_dir / "paper" / "main.tex").exists()
    assert (latex_dir / "paper" / "main.tex").is_file()
    assert not (latex_dir / "res.md").exists()


def test_latex_failure_writes_failed_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    prepare_latex_source(tmp_path, _sections(), [])
    for stale_name in ("paper.pdf", "paper-source.zip", "all.zip"):
        (tmp_path / stale_name).write_bytes(b"stale-success-artifact")
    monkeypatch.setattr(paper_artifacts, "get_work_dir", lambda _task_id: str(tmp_path))
    monkeypatch.setattr(paper_artifacts.shutil, "which", lambda _name: None)
    monkeypatch.delenv("XELATEX_BIN", raising=False)

    with pytest.raises(PaperArtifactError, match="XeLaTeX"):
        paper_artifacts.finalize_task_output("test-task", FormatOutPut.LaTeX)

    manifest = json.loads(
        (tmp_path / "artifact_manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["status"] == "failed"
    assert manifest["primary_artifact"] is None
    assert manifest["error_stage"] == "compiler_discovery"
    assert not (tmp_path / "paper.pdf").exists()
    assert not (tmp_path / "paper-source.zip").exists()
    assert not (tmp_path / "all.zip").exists()


def test_vector_assets_are_preferred_over_png_previews():
    selected = BaseCodeInterpreter.prefer_vector_images(
        ["trend.png", "trend.pdf", "distribution.jpg", "distribution.png"]
    )
    assert selected == ["distribution.png", "trend.pdf"]


def test_repeated_latex_reference_keeps_one_bibliography_entry(tmp_path: Path):
    output = UserOutput(str(tmp_path), ques_count=1)
    for key, value in _sections(question_count=1).items():
        output.res[key] = {"response_content": value, "footnotes": []}
    reference = "{[^1]: 张三. 同一篇文献[J]. 测试期刊, 2024.}"
    output.res["analysisQues"]["response_content"] += reference
    output.res["ques1"]["response_content"] += reference
    sections, references = output.get_latex_sections()
    assert references == ["张三. 同一篇文献[J]. 测试期刊, 2024"]
    assert sections["analysisQues"].count(r"\cite{ref1}") == 1
    assert sections["ques1"].count(r"\cite{ref1}") == 1


def test_pdf_sparse_page_check_ignores_footer_page_number(tmp_path: Path):
    pdf_path = tmp_path / "sparse.pdf"
    document = fitz.open()
    for index in range(3):
        page = document.new_page(width=595.28, height=841.89)
        for line in range(15):
            page.insert_text(
                (72, 90 + line * 10),
                f"Page {index + 1} body text line {line + 1} for occupancy testing",
            )
        page.insert_text((292, 810), str(index + 1))
    document.save(pdf_path)
    document.close()

    with pytest.raises(PaperArtifactError, match="正文页版心纵向占用低于 60%: 2"):
        _inspect_pdf(pdf_path)


@pytest.mark.parametrize(
    "log_text",
    [
        "LaTeX Warning: There were undefined citations.",
        "Overfull \\hbox (3.5pt too wide) in paragraph",
        "No file missing-figure.pdf.",
    ],
)
def test_compile_log_rejects_unresolved_or_overflowing_output(log_text: str):
    with pytest.raises(PaperArtifactError):
        _validate_compile_log(log_text)


@pytest.mark.skipif(shutil.which("xelatex") is None, reason="XeLaTeX is unavailable")
def test_compile_latex_fixture_and_package_artifacts(tmp_path: Path):
    prepare_latex_source(tmp_path, _sections(), [])
    manifest = _compile_latex(tmp_path)

    assert manifest["status"] == "success"
    assert manifest["compile_passes"] == 2
    assert manifest["checks"]["a4_portrait"] is True
    assert manifest["checks"]["rendered_pages"] >= 1
    assert manifest["checks"]["no_placeholders"] is True
    assert manifest["checks"]["headings_black"] is True
    assert (tmp_path / "paper.pdf").is_file()
    assert (tmp_path / "paper-source.zip").is_file()
    assert (tmp_path / "compile.log").is_file()
    assert (tmp_path / "all.zip").is_file()
    with zipfile.ZipFile(tmp_path / "paper-source.zip") as archive:
        assert "main.tex" in archive.namelist()
        assert "main.pdf" not in archive.namelist()
    with zipfile.ZipFile(tmp_path / "all.zip") as archive:
        names = set(archive.namelist())
        assert {
            "paper.pdf",
            "paper-source.zip",
            "compile.log",
            "artifact_manifest.json",
        } <= names
