#!/usr/bin/env python3
"""Compile and verify a CUMCM LaTeX paper with deterministic hard gates."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import fitz


def fail(message: str) -> None:
    raise RuntimeError(message)


def compile_twice(paper_dir: Path) -> Path:
    executable = shutil.which("xelatex")
    if not executable:
        fail("xelatex is unavailable")
    outputs = []
    for pass_index in range(1, 3):
        command = [executable]
        if "miktex" in executable.lower():
            command.append("--disable-installer")
        command += ["-interaction=nonstopmode", "-halt-on-error", "main.tex"]
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
        outputs.append(
            f"===== XeLaTeX pass {pass_index} =====\n{result.stdout}\n{result.stderr}"
        )
        if result.returncode:
            (paper_dir / "compile.log").write_text("\n".join(outputs), encoding="utf-8")
            fail(f"xelatex pass {pass_index} failed")
    (paper_dir / "compile.log").write_text("\n".join(outputs), encoding="utf-8")
    inspect_compile_log(
        (paper_dir / "main.log").read_text(encoding="utf-8", errors="replace")
    )
    return paper_dir / "main.pdf"


def inspect_compile_log(text: str) -> None:
    fatal_patterns = (
        r"! LaTeX Error:",
        r"Undefined control sequence",
        r"LaTeX Warning: There were undefined (?:references|citations)",
        r"LaTeX Warning: (?:Citation|Reference) .+ undefined",
        r"No file .+\.(?:tex|bib|png|jpe?g|pdf)",
        r"Package .* Error:",
        r"Emergency stop",
    )
    for pattern in fatal_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            fail(f"compile log hard gate failed: {pattern}")
    for width in re.findall(
        r"Overfull \\[hv]box \(([0-9.]+)pt too (?:wide|high)\)", text
    ):
        if float(width) > 3.0:
            fail(f"overfull box exceeds 3pt: {width}pt")


def inspect_source(paper_dir: Path) -> None:
    tex_files = sorted(paper_dir.rglob("*.tex"))
    if not tex_files:
        fail("paper_dir contains no LaTeX sources")
    text = "\n".join(
        path.read_text(encoding="utf-8", errors="replace") for path in tex_files
    )
    forbidden = (
        r"(?:生成|验收)时间\s*[:：]",
        r"(?:Agent|模型|系统)\s*版本\s*[:：]",
        r"\\(?:pagecolor|textcolor|newpage|clearpage)\b",
        r"(?m)^\s*#{1,6}\s+",
        r"%%PAPER_[A-Z_]+%%|(?:TODO|PLACEHOLDER|待补充|待续写|搜索文献失败|执行过程中遇到错误)",
    )
    for pattern in forbidden:
        if re.search(pattern, text, re.IGNORECASE):
            fail(f"source hard gate failed: {pattern}")
    if text.count(r"\section*{参考文献}") > 1:
        fail("duplicate reference headings")
    colors = re.findall(r"\\(?:color|textcolor)\s*\{([^{}]+)\}", text)
    if any(
        color.strip().lower() not in {"black", "paperblack"}
        and not color.strip().lower().startswith("black!")
        for color in colors
    ):
        fail("non-black explicit color")


def inspect_pdf(
    pdf_path: Path,
    render_dir: Path | None,
    minimum_main_pages: int = 0,
) -> dict[str, object]:
    document = fitz.open(pdf_path)
    if not document.page_count:
        fail("empty PDF")
    sparse = []
    extracted = 0
    extracted_parts = []
    visual_exemptions = []
    page_occupancies = []
    reference_heading_pages = []
    if render_dir:
        render_dir.mkdir(parents=True, exist_ok=True)
    for index, page in enumerate(document):
        if abs(page.rect.width - 595.28) > 3 or abs(page.rect.height - 841.89) > 3:
            fail(f"page {index + 1} is not A4 portrait")
        text = page.get_text().strip()
        extracted += len(text)
        extracted_parts.append(text)
        if "参考文献" in text:
            reference_heading_pages.append(index + 1)
        if "�" in text:
            fail(f"page {index + 1} contains replacement glyphs")
        pixmap = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)
        dominant_ratio, dominant_color = pixmap.color_topusage()
        if dominant_ratio > 0.999 and min(dominant_color[:3]) > 245:
            fail(f"page {index + 1} appears blank")
        if render_dir:
            pixmap.save(render_dir / f"page-{index + 1:03d}.png")
        usable_bottom = page.rect.height - 60.0
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
        rects = [*text_rects, *visual_rects]
        if rects:
            top = max(60.0, min(rect.y0 for rect in rects))
            bottom = min(usable_bottom, max(rect.y1 for rect in rects))
            occupancy = max(0.0, bottom - top) / (page.rect.height - 120.0)
        else:
            occupancy = 0.0
        page_occupancies.append(round(occupancy, 4))
        if 0 < index < document.page_count - 1:
            if occupancy < 0.60:
                sparse.append(index + 1)
            elif visual_rects and not text_rects:
                visual_exemptions.append(index + 1)
    if extracted < 20:
        fail("insufficient extractable text")
    if sparse:
        fail(f"sparse interior pages: {sparse}")
    if not re.search(r"[\u3400-\u9fff]", "\n".join(extracted_parts)):
        fail("PDF has no extractable Chinese text")
    reference_start_page = (
        reference_heading_pages[-1] if reference_heading_pages else None
    )
    main_text_pages = document.page_count
    if reference_start_page is not None:
        page = document[reference_start_page - 1]
        heading_rects = page.search_for("参考文献")
        heading_y = min((rect.y0 for rect in heading_rects), default=0.0)
        main_text_pages = (
            reference_start_page
            if heading_y > page.rect.height * 0.30
            else reference_start_page - 1
        )
    if minimum_main_pages:
        if reference_start_page is None:
            fail("cannot determine main-text pages without a 参考文献 heading")
        if main_text_pages < minimum_main_pages:
            fail(
                "main text is shorter than benchmark floor: "
                f"{main_text_pages} < {minimum_main_pages} pages"
            )
    return {
        "pages": document.page_count,
        "a4": True,
        "sparse_pages": [],
        "full_page_visual_exemptions": visual_exemptions,
        "reference_start_page": reference_start_page,
        "main_text_pages": main_text_pages,
        "page_occupancies": page_occupancies,
        "last_page_occupancy": page_occupancies[-1],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paper_dir", type=Path)
    parser.add_argument("--skip-compile", action="store_true")
    parser.add_argument("--render-dir", type=Path)
    parser.add_argument("--minimum-main-pages", type=int, default=0)
    args = parser.parse_args()
    paper_dir = args.paper_dir.resolve()
    main_tex = paper_dir / "main.tex"
    if not main_tex.is_file():
        fail("paper_dir must contain main.tex")
    if args.minimum_main_pages < 0:
        fail("minimum-main-pages must be non-negative")
    inspect_source(paper_dir)
    pdf_path = paper_dir / "main.pdf" if args.skip_compile else compile_twice(paper_dir)
    result = inspect_pdf(pdf_path, args.render_dir, args.minimum_main_pages)
    print(json.dumps({"status": "passed", **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        sys.exit(1)
