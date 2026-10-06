"""LaTeX paper assembly, compilation, validation, and packaging."""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path
from typing import Any

import fitz  # type: ignore[import-unresolved]

from app.core.quality_gates import QualityGateError, validate_competition_paper_text
from app.schemas.enums import FormatOutPut
from app.utils.common_utils import get_work_dir, md_2_docx


class PaperArtifactError(RuntimeError):
    """Raised when a requested paper artifact cannot pass its hard gates."""

    def __init__(
        self,
        message: str,
        *,
        stage: str = "validation",
        compile_passes: int = 0,
    ) -> None:
        super().__init__(message)
        self.stage = stage
        self.compile_passes = compile_passes


_FORBIDDEN_LATEX = re.compile(
    r"\\(?:documentclass|usepackage|begin\s*\{document\}|end\s*\{document\}|"
    r"titleformat|pagecolor|color\b|textcolor\b|newpage|clearpage|includeonly|write18)"
)
_MARKDOWN_HEADING = re.compile(r"(?m)^\s*#{1,6}\s+")
_MARKDOWN_IMAGE = re.compile(r"!\[[^]]*]\([^)]+\)")
_INCLUDE_GRAPHICS = re.compile(
    r"\\includegraphics(?P<options>\[[^]]*])?\{(?P<path>[^{}]+)\}"
)
_FRONT_TAGS = {
    "title": "PAPER_TITLE",
    "abstract": "PAPER_ABSTRACT",
    "keywords": "PAPER_KEYWORDS",
}
_A4_WIDTH_PT = 595.28
_A4_HEIGHT_PT = 841.89


def _escape_latex_text(text: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in text.strip())


def _extract_front_matter(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for key, tag in _FRONT_TAGS.items():
        match = re.search(
            rf"<{tag}>\s*(.*?)\s*</{tag}>", text, flags=re.DOTALL | re.IGNORECASE
        )
        if not match or not match.group(1).strip():
            raise PaperArtifactError(f"LaTeX 首页缺少 <{tag}> 字段")
        values[key] = match.group(1).strip()
    remainder = text
    for tag in _FRONT_TAGS.values():
        remainder = re.sub(
            rf"<{tag}>.*?</{tag}>",
            "",
            remainder,
            flags=re.DOTALL | re.IGNORECASE,
        )
    if remainder.strip():
        raise PaperArtifactError("LaTeX 首页标签外包含额外文字")
    return values


def _validate_fragment(text: str, section_name: str) -> None:
    if _FORBIDDEN_LATEX.search(text):
        raise PaperArtifactError(f"{section_name} 包含禁止由 Writer 控制的 LaTeX 命令")
    if _MARKDOWN_HEADING.search(text) or _MARKDOWN_IMAGE.search(text):
        raise PaperArtifactError(f"{section_name} 混入 Markdown 语法")


def _copy_graphics(work_dir: Path, paper_dir: Path, text: str) -> str:
    figures_dir = paper_dir / "figures"
    figures_dir.mkdir(parents=True, exist_ok=True)
    name_counts: dict[str, int] = {}

    def replace(match: re.Match[str]) -> str:
        raw_path = match.group("path").strip().replace("\\", "/")
        source_rel = Path(raw_path)
        if source_rel.is_absolute() or ".." in source_rel.parts:
            raise PaperArtifactError(f"图片路径必须位于任务目录内: {raw_path}")
        source = (work_dir / source_rel).resolve()
        try:
            source.relative_to(work_dir.resolve())
        except ValueError as exc:
            raise PaperArtifactError(f"图片路径越出任务目录: {raw_path}") from exc
        if not source.is_file():
            raise PaperArtifactError(f"论文引用的图片不存在: {raw_path}")

        stem = re.sub(r"[^A-Za-z0-9_.-]+", "-", source.stem).strip("-") or "figure"
        suffix = source.suffix.lower()
        name_counts[stem] = name_counts.get(stem, 0) + 1
        serial = "" if name_counts[stem] == 1 else f"-{name_counts[stem]}"
        output_suffix = ".pdf" if suffix == ".svg" else suffix
        if output_suffix not in {".pdf", ".png", ".jpg", ".jpeg"}:
            raise PaperArtifactError(f"LaTeX 不支持的图片格式: {raw_path}")
        target = figures_dir / f"{stem}{serial}{output_suffix}"
        if suffix == ".svg":
            try:
                svg_document = fitz.open("svg", source.read_bytes())
                pdf_bytes = svg_document.convert_to_pdf()
                target.write_bytes(pdf_bytes)
            except Exception as exc:
                raise PaperArtifactError(f"SVG 转 PDF 失败: {raw_path}") from exc
        else:
            shutil.copy2(source, target)
        options = match.group("options") or ""
        return rf"\includegraphics{options}{{figures/{target.name}}}"

    return _INCLUDE_GRAPHICS.sub(replace, text)


def prepare_latex_source(
    work_dir: str | Path,
    sections: dict[str, str],
    references: list[str],
) -> Path:
    """Assemble validated Writer fragments into the controlled CUMCM template."""
    work_path = Path(work_dir).resolve()
    paper_dir = work_path / "paper"
    if paper_dir.exists():
        shutil.rmtree(paper_dir)
    paper_dir.mkdir(parents=True)

    if "firstPage" not in sections:
        raise PaperArtifactError("论文缺少 firstPage")
    try:
        validate_competition_paper_text(
            "\n".join(sections.values()), section_name="assembled_latex_paper"
        )
    except QualityGateError as exc:
        raise PaperArtifactError(str(exc)) from exc
    front = _extract_front_matter(sections["firstPage"])
    _validate_fragment(front["abstract"], "firstPage.abstract")

    body_parts: list[str] = []
    for name, fragment in sections.items():
        if name == "firstPage":
            continue
        _validate_fragment(fragment, name)
        body_parts.append(fragment.strip())
    body = _copy_graphics(work_path, paper_dir, "\n\n".join(body_parts))

    keyword_parts = [
        item
        for item in re.split(r"[,，;；、\s]+", front["keywords"])
        if item.strip()
    ]
    keywords = r" \quad ".join(_escape_latex_text(item) for item in keyword_parts)
    bibliography = ""
    if references:
        items = "\n".join(
            rf"\bibitem{{ref{index}}} {_escape_latex_text(reference)}"
            for index, reference in enumerate(references, start=1)
        )
        bibliography = (
            "\\section*{参考文献}\n"
            "\\addcontentsline{toc}{section}{参考文献}\n"
            "\\begin{thebibliography}{99}\n"
            f"{items}\n"
            "\\end{thebibliography}"
        )

    template_path = Path(__file__).resolve().parents[1] / "templates" / "cumcm" / "main.tex"
    template = template_path.read_text(encoding="utf-8")
    rendered = (
        template.replace("%%PAPER_TITLE%%", _escape_latex_text(front["title"]))
        .replace("%%PAPER_ABSTRACT%%", front["abstract"])
        .replace("%%PAPER_KEYWORDS%%", keywords)
        .replace("%%PAPER_BODY%%", body)
        .replace("%%PAPER_REFERENCES%%", bibliography)
    )
    main_tex = paper_dir / "main.tex"
    main_tex.write_text(rendered, encoding="utf-8")
    return main_tex


def _validate_compile_log(log_text: str) -> None:
    fatal_patterns = (
        r"! LaTeX Error:",
        r"Undefined control sequence",
        r"LaTeX Warning: There were undefined references",
        r"LaTeX Warning: There were undefined citations",
        r"LaTeX Warning: Citation .+ undefined",
        r"LaTeX Warning: Reference .+ undefined",
        r"No file .+\.(?:tex|bib|png|jpe?g|pdf)",
        r"Package .* Error:",
        r"Emergency stop",
    )
    for pattern in fatal_patterns:
        if re.search(pattern, log_text, flags=re.IGNORECASE):
            raise PaperArtifactError(
                f"LaTeX 日志未通过硬门禁: {pattern}",
                stage="log_validation",
                compile_passes=2,
            )
    overfull = re.findall(
        r"Overfull \\[hv]box \(([0-9.]+)pt too (?:wide|high)\)", log_text
    )
    for width in overfull:
        if float(width) > 3.0:
            raise PaperArtifactError(
                f"LaTeX 版心溢出 {width}pt，超过 3pt 门槛",
                stage="log_validation",
                compile_passes=2,
            )


def _validate_assembled_source(main_tex: Path) -> dict[str, Any]:
    text = main_tex.read_text(encoding="utf-8")
    try:
        validate_competition_paper_text(text, section_name="assembled_latex_source")
    except QualityGateError as exc:
        raise PaperArtifactError(str(exc), stage="source_validation") from exc
    if re.search(
        r"%%PAPER_[A-Z_]+%%|(?:TODO|PLACEHOLDER|待补充|待续写|搜索文献失败|执行过程中遇到错误)",
        text,
        flags=re.IGNORECASE,
    ):
        raise PaperArtifactError("LaTeX 源码包含占位符或未替换模板字段", stage="source_validation")
    if text.count(r"\section*{参考文献}") > 1:
        raise PaperArtifactError("LaTeX 源码包含重复参考文献标题", stage="source_validation")
    explicit_colors = re.findall(r"\\(?:color|textcolor)\s*\{([^{}]+)\}", text)
    if any(
        color.strip().lower() not in {"black", "paperblack"}
        and not color.strip().lower().startswith("black!")
        for color in explicit_colors
    ):
        raise PaperArtifactError("LaTeX 标题或正文包含非黑色显式颜色", stage="source_validation")
    return {
        "no_placeholders": True,
        "no_process_metadata": True,
        "single_reference_heading": True,
        "headings_black": True,
        "referenced_images_exist": True,
        "image_references": len(_INCLUDE_GRAPHICS.findall(text)),
    }


def _inspect_pdf(pdf_path: Path) -> dict[str, Any]:
    document = fitz.open(pdf_path)
    if document.page_count == 0:
        raise PaperArtifactError("PDF 没有页面")

    sparse_pages: list[int] = []
    rendered_pages = 0
    extracted_chars = 0
    extracted_text_parts: list[str] = []
    visual_exemptions: list[int] = []
    for index, page in enumerate(document):
        width, height = page.rect.width, page.rect.height
        if abs(width - _A4_WIDTH_PT) > 3 or abs(height - _A4_HEIGHT_PT) > 3:
            raise PaperArtifactError(f"第 {index + 1} 页不是 A4 纵向页面")
        text = page.get_text().strip()
        extracted_chars += len(text)
        extracted_text_parts.append(text)
        if "�" in text:
            raise PaperArtifactError(f"第 {index + 1} 页存在不可提取字符")

        pixmap = page.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
        dominant_ratio, dominant_color = pixmap.color_topusage()
        if dominant_ratio > 0.999 and min(dominant_color[:3]) > 245:
            raise PaperArtifactError(f"第 {index + 1} 页疑似空白页")
        rendered_pages += 1

        if 0 < index < document.page_count - 1:
            usable_bottom = height - 60.0
            usable_top = 60.0
            text_rects = [
                fitz.Rect(block[:4])
                for block in page.get_text("blocks")
                if block[4].strip() and block[1] < usable_bottom
            ]
            visual_rects = [
                fitz.Rect(item["bbox"])
                for item in page.get_image_info()
                if fitz.Rect(item["bbox"]).y0 < usable_bottom
            ]
            visual_rects.extend(
                drawing["rect"]
                for drawing in page.get_drawings()
                if drawing["rect"].height > 3 and drawing["rect"].y0 < usable_bottom
            )
            content_rects = [*text_rects, *visual_rects]
            if not content_rects:
                sparse_pages.append(index + 1)
                continue
            content_top = max(usable_top, min(rect.y0 for rect in content_rects))
            content_bottom = min(usable_bottom, max(rect.y1 for rect in content_rects))
            occupancy = max(0.0, content_bottom - content_top) / (
                usable_bottom - usable_top
            )
            if occupancy < 0.60:
                sparse_pages.append(index + 1)
            elif visual_rects and not text_rects:
                visual_exemptions.append(index + 1)

    if extracted_chars < 20:
        raise PaperArtifactError("PDF 未提取到足够正文文本")
    if sparse_pages:
        pages = ", ".join(str(page) for page in sparse_pages)
        raise PaperArtifactError(f"正文页版心纵向占用低于 60%: {pages}")
    if not re.search(r"[\u3400-\u9fff]", "\n".join(extracted_text_parts)):
        raise PaperArtifactError("PDF 未提取到中文正文")
    return {
        "a4_portrait": True,
        "text_extractable": True,
        "rendered_pages": rendered_pages,
        "sparse_body_pages": [],
        "full_page_visual_exemptions": visual_exemptions,
    }


def _write_source_archive(paper_dir: Path, target: Path) -> None:
    excluded = {"main.aux", "main.log", "main.out", "main.pdf", "main.toc"}
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(paper_dir.rglob("*")):
            if path.is_file() and path.name not in excluded:
                archive.write(path, path.relative_to(paper_dir))


def _write_all_archive(work_dir: Path) -> None:
    target = work_dir / "all.zip"
    with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(work_dir.rglob("*")):
            if not path.is_file() or path == target:
                continue
            relative = path.relative_to(work_dir)
            if relative.parts and relative.parts[0] == "paper":
                continue
            archive.write(path, relative)


def _write_manifest(work_dir: Path, payload: dict[str, Any]) -> None:
    (work_dir / "artifact_manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _compile_latex(work_dir: Path) -> dict[str, Any]:
    for name in (
        "paper.pdf",
        "paper-source.zip",
        "compile.log",
        "artifact_manifest.json",
        "all.zip",
    ):
        (work_dir / name).unlink(missing_ok=True)
    paper_dir = work_dir / "paper"
    main_tex = paper_dir / "main.tex"
    if not main_tex.is_file():
        raise PaperArtifactError("缺少 paper/main.tex", stage="source_validation")
    source_checks = _validate_assembled_source(main_tex)
    executable = os.getenv("XELATEX_BIN") or shutil.which("xelatex")
    if not executable:
        raise PaperArtifactError(
            "未找到 XeLaTeX，请安装 xelatex 或设置 XELATEX_BIN",
            stage="compiler_discovery",
        )

    pass_outputs: list[str] = []
    for pass_index in range(1, 3):
        command = [executable]
        if "miktex" in executable.lower():
            command.append("--disable-installer")
        command.extend(
            ["-interaction=nonstopmode", "-halt-on-error", "main.tex"]
        )
        try:
            result = subprocess.run(
                command,
                cwd=paper_dir,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=180,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise PaperArtifactError(
                f"XeLaTeX 第 {pass_index} 遍编译超时",
                stage=f"compile_pass_{pass_index}",
                compile_passes=pass_index - 1,
            ) from exc
        output = f"===== XeLaTeX pass {pass_index} =====\n{result.stdout}\n{result.stderr}"
        pass_outputs.append(output)
        if result.returncode != 0:
            (work_dir / "compile.log").write_text("\n".join(pass_outputs), encoding="utf-8")
            raise PaperArtifactError(
                f"XeLaTeX 第 {pass_index} 遍编译失败",
                stage=f"compile_pass_{pass_index}",
                compile_passes=pass_index - 1,
            )

    compile_log = "\n".join(pass_outputs)
    (work_dir / "compile.log").write_text(compile_log, encoding="utf-8")
    final_log = (paper_dir / "main.log").read_text(encoding="utf-8", errors="replace")
    _validate_compile_log(final_log)
    pdf_path = paper_dir / "main.pdf"
    if not pdf_path.is_file():
        raise PaperArtifactError("XeLaTeX 未生成 main.pdf")
    try:
        checks = _inspect_pdf(pdf_path)
    except PaperArtifactError as exc:
        raise PaperArtifactError(
            str(exc), stage="pdf_validation", compile_passes=2
        ) from exc

    shutil.copy2(pdf_path, work_dir / "paper.pdf")
    _write_source_archive(paper_dir, work_dir / "paper-source.zip")
    manifest = {
        "format": FormatOutPut.LaTeX.value,
        "status": "success",
        "primary_artifact": "paper.pdf",
        "source_archive": "paper-source.zip",
        "compiler": "xelatex",
        "compile_passes": 2,
        "checks": {
            "compiled": True,
            "references_resolved": True,
            "overfull_boxes_within_3pt": True,
            **source_checks,
            **checks,
        },
        "files": [
            "paper.pdf",
            "paper-source.zip",
            "compile.log",
            "artifact_manifest.json",
            "all.zip",
        ],
    }
    _write_manifest(work_dir, manifest)
    _write_all_archive(work_dir)
    return manifest


def finalize_task_output(task_id: str, format_output: FormatOutPut) -> dict[str, Any] | None:
    """Finalize the selected output format before a task may report success."""
    if format_output == FormatOutPut.Markdown:
        md_2_docx(task_id)
        return None

    work_dir = Path(get_work_dir(task_id)).resolve()
    try:
        return _compile_latex(work_dir)
    except Exception as exc:
        _write_manifest(
            work_dir,
            {
                "format": FormatOutPut.LaTeX.value,
                "status": "failed",
                "primary_artifact": None,
                "source_archive": None,
                "compiler": "xelatex",
                "compile_passes": getattr(exc, "compile_passes", 0),
                "checks": {"compiled": False},
                "files": [
                    name
                    for name in ("compile.log", "artifact_manifest.json")
                    if (work_dir / name).exists() or name == "artifact_manifest.json"
                ],
                "error_stage": getattr(exc, "stage", "finalization"),
                "error": str(exc),
            },
        )
        if isinstance(exc, PaperArtifactError):
            raise
        raise PaperArtifactError(str(exc)) from exc
