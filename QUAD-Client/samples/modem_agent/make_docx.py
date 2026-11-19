r"""Convert the modem_agent markdown docs to .docx for sharing.

Reads:
  docs/requirements.md
  docs/design.md
  docs/open_questions.md

Writes alongside each .md file a corresponding .docx with the same name.

The converter handles:
  - Headings (h1-h4)
  - Paragraphs with **bold**, *italic*, and `code` inline runs
  - Tables (Markdown pipe tables with header row + separator)
  - Bullet lists
  - Fenced code blocks (rendered in Consolas)
  - Horizontal rules (skipped)

Run:
  ..\stc_classifier\.venv\Scripts\python.exe make_docx.py

Dependency: python-docx>=1.1 (install once with
`uv pip install --python <venv> python-docx`).
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from docx import Document
from docx.shared import Pt, RGBColor

HERE = Path(__file__).resolve().parent
DOCS_DIR = HERE / "docs"
SOURCES = ["requirements.md", "design.md", "open_questions.md"]

# Inline tokens: **bold**, *italic*, `code`
_INLINE_RE = re.compile(r"(\*\*[^*]+\*\*|`[^`]+`|\*[^*\s][^*]*\*)")


def apply_inline(paragraph, text: str) -> None:
    """Walk inline markdown tokens and add Runs with the right formatting."""
    pos = 0
    for m in _INLINE_RE.finditer(text):
        if m.start() > pos:
            paragraph.add_run(text[pos:m.start()])
        token = m.group(0)
        if token.startswith("**"):
            run = paragraph.add_run(token[2:-2])
            run.bold = True
        elif token.startswith("`"):
            run = paragraph.add_run(token[1:-1])
            run.font.name = "Consolas"
            run.font.size = Pt(10)
        elif token.startswith("*"):
            run = paragraph.add_run(token[1:-1])
            run.italic = True
        pos = m.end()
    if pos < len(text):
        paragraph.add_run(text[pos:])


def md_to_docx(md_path: Path, docx_path: Path) -> None:
    """Convert one markdown file to one docx file."""
    doc = Document()

    # Tighten the default body style
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    lines = md_path.read_text(encoding="utf-8").splitlines()

    in_code = False
    code_lines: list[str] = []
    table_rows: list[list[str]] = []

    def flush_code() -> None:
        if not code_lines:
            return
        p = doc.add_paragraph()
        run = p.add_run("\n".join(code_lines))
        run.font.name = "Consolas"
        run.font.size = Pt(9)
        run.font.color.rgb = RGBColor(0x33, 0x33, 0x33)
        code_lines.clear()

    def flush_table() -> None:
        if not table_rows:
            return
        # row 0 = header, row 1 = separator (---), rows 2+ = body
        header = table_rows[0]
        body = [r for r in table_rows[2:] if any(c.strip() for c in r)]
        cols = max(len(header), max((len(r) for r in body), default=0))
        if cols == 0:
            table_rows.clear()
            return
        tbl = doc.add_table(rows=1 + len(body), cols=cols)
        try:
            tbl.style = "Light Grid Accent 1"
        except KeyError:
            tbl.style = "Table Grid"
        # Header
        for ci in range(cols):
            cell_text = header[ci] if ci < len(header) else ""
            cell = tbl.cell(0, ci)
            cell.text = ""
            p = cell.paragraphs[0]
            run = p.add_run(cell_text)
            run.bold = True
        # Body
        for ri, row in enumerate(body):
            for ci in range(cols):
                cell_text = row[ci] if ci < len(row) else ""
                cell = tbl.cell(ri + 1, ci)
                cell.text = ""
                p = cell.paragraphs[0]
                apply_inline(p, cell_text)
        # Spacer paragraph after the table so following content isn't glued
        doc.add_paragraph()
        table_rows.clear()

    in_table = False
    for raw in lines:
        line = raw.rstrip("\r")

        # Code fence toggles
        if line.startswith("```"):
            if in_code:
                flush_code()
                in_code = False
            else:
                if in_table:
                    flush_table()
                    in_table = False
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue

        # Tables
        if line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            table_rows.append(cells)
            in_table = True
            continue
        if in_table:
            flush_table()
            in_table = False

        # Horizontal rule -> skip (visual only)
        if re.fullmatch(r"-{3,}|_{3,}|\*{3,}", line.strip()):
            continue

        # Heading
        m = re.match(r"^(#{1,6})\s+(.*)$", line)
        if m:
            level = min(len(m.group(1)), 4)
            heading = doc.add_heading(level=level)
            apply_inline(heading, m.group(2).strip())
            continue

        # Bullet list
        if re.match(r"^[\*\-]\s+", line):
            text = re.sub(r"^[\*\-]\s+", "", line)
            p = doc.add_paragraph(style="List Bullet")
            apply_inline(p, text)
            continue

        # Numbered list
        if re.match(r"^\d+\.\s+", line):
            text = re.sub(r"^\d+\.\s+", "", line)
            p = doc.add_paragraph(style="List Number")
            apply_inline(p, text)
            continue

        # Blockquote -> indent + italic
        if line.startswith("> "):
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Pt(18)
            run = p.add_run(line[2:])
            run.italic = True
            continue

        # Empty line -> nothing (paragraph break is implicit)
        if not line.strip():
            continue

        # Default: paragraph
        p = doc.add_paragraph()
        apply_inline(p, line)

    # Flush trailing buffers
    if in_code:
        flush_code()
    if in_table:
        flush_table()

    doc.save(docx_path)


def main() -> int:
    if not DOCS_DIR.is_dir():
        print(f"docs dir not found: {DOCS_DIR}", file=sys.stderr)
        return 1
    converted = []
    for name in SOURCES:
        md = DOCS_DIR / name
        if not md.is_file():
            print(f"  SKIP   {name} (not found)")
            continue
        docx = md.with_suffix(".docx")
        md_to_docx(md, docx)
        size_kb = docx.stat().st_size / 1024
        converted.append((md.name, docx.name, size_kb))
        print(f"  WROTE  {docx.name} ({size_kb:.1f} KB)")
    print()
    print(f"Converted {len(converted)} files in {DOCS_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
