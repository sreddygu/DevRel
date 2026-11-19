"""Extract DOCX reference text and inventory a QLI workbook.

DOCX extraction uses only the Python standard library. Workbook inventory needs
``openpyxl`` and reports a clear installation error only when that operation is
requested, allowing ``--help`` to work on minimal Python environments.
"""

import argparse
import json
import zipfile
from pathlib import Path
from xml.etree import ElementTree

WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def extract_docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        document_xml = archive.read("word/document.xml")

    root = ElementTree.fromstring(document_xml)
    namespace = {"w": WORD_NAMESPACE}
    lines = []
    for paragraph in root.findall(".//w:p", namespace):
        text = "".join(
            node.text or "" for node in paragraph.findall(".//w:t", namespace)
        ).strip()
        if text:
            lines.append(text)
    return "\n".join(lines) + "\n"


def audit_workbook(path: Path) -> dict:
    """Return workbook sheets, dimensions, and non-empty row values."""
    try:
        import openpyxl
    except ModuleNotFoundError as error:
        raise SystemExit(
            "Workbook inventory requires openpyxl. Install it with: "
            "python -m pip install openpyxl"
        ) from error
    workbook = openpyxl.load_workbook(path, data_only=False)
    result = {"path": str(path), "sheets": []}
    for sheet in workbook.worksheets:
        rows = []
        for row in sheet.iter_rows():
            values = [cell.value for cell in row]
            if any(value is not None for value in values):
                rows.append(values)
        result["sheets"].append(
            {
                "name": sheet.title,
                "dimensions": sheet.calculate_dimension(),
                "rows": rows,
            }
        )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract QLI DOCX text and inventory the dogfooding workbook."
    )
    parser.add_argument("--reference-dir", type=Path, required=True)
    parser.add_argument("--workbook", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    for docx_path in sorted(args.reference_dir.glob("*.docx")):
        output_path = args.output_dir / f"{docx_path.stem}.txt"
        output_path.write_text(extract_docx_text(docx_path), encoding="utf-8")

    report_path = args.output_dir / "workbook_inventory.json"
    report_path.write_text(
        json.dumps(audit_workbook(args.workbook), indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
