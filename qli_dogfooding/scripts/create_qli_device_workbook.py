"""Create a device-specific QLI dogfooding workbook from normalized evidence.

The builder preserves the established template's formatting, applies explicit
placeholder or caller-supplied replacements, and updates persona, inventory,
workflow, completion, and friction sheets by semantic row names. It requires
``openpyxl``.
"""

import argparse
import copy
import json
from datetime import date
from pathlib import Path

import openpyxl
from openpyxl.styles import PatternFill


STATUS_COLORS = {
    "Completed": "E2EFDA",
    "User Completed": "DDEBF7",
    "Partial": "FFF2CC",
    "Blocked": "F4CCCC",
    "Not Tested": "D9D9D9",
    "Not Applicable": "D9D9D9",
}


def read_summary(path: Path) -> dict:
    """Read the normalized summary JSON."""
    return json.loads(path.read_text(encoding="utf-8"))


def parse_replacements(values: list[str]) -> dict[str, str]:
    """Parse repeated OLD=NEW command-line replacements."""
    replacements = {}
    for value in values:
        if "=" not in value:
            raise ValueError(f"Replacement must use OLD=NEW syntax: {value}")
        old, new = value.split("=", 1)
        if not old:
            raise ValueError("Replacement source text cannot be empty")
        replacements[old] = new
    return replacements


def replace_text(workbook, replacements: dict[str, str]) -> None:
    """Replace legacy device text in every string cell."""
    for sheet in workbook.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                if not isinstance(cell.value, str):
                    continue
                value = cell.value
                for old, new in replacements.items():
                    value = value.replace(old, new)
                cell.value = value


def find_row(sheet, column: int, value: str) -> int:
    """Find a one-based row by exact string value in a column."""
    for row in range(2, sheet.max_row + 1):
        if str(sheet.cell(row, column).value or "") == value:
            return row
    return 0


def copy_row_style(sheet, source_row: int, target_row: int, columns: int) -> None:
    """Copy cell styles, dimensions, and number formats between rows."""
    sheet.row_dimensions[target_row].height = sheet.row_dimensions[source_row].height
    for column in range(1, columns + 1):
        source = sheet.cell(source_row, column)
        target = sheet.cell(target_row, column)
        if source.has_style:
            target._style = copy.copy(source._style)
        target.font = copy.copy(source.font)
        target.fill = copy.copy(source.fill)
        target.border = copy.copy(source.border)
        target.alignment = copy.copy(source.alignment)
        target.protection = copy.copy(source.protection)
        target.number_format = source.number_format


def set_status(cell, status: str) -> None:
    """Set a status value and its workbook fill color."""
    cell.value = status
    color = STATUS_COLORS.get(status, "FFFFFF")
    cell.fill = PatternFill(fill_type="solid", fgColor=color)


def clear_rows(sheet, start_row: int, end_row: int, columns: int) -> None:
    """Clear values while retaining template formatting."""
    for row in range(start_row, end_row + 1):
        for column in range(1, columns + 1):
            sheet.cell(row, column).value = None


def populate_workbook(workbook, summary: dict, replacements: dict[str, str]) -> None:
    """Populate all workbook sheets from the normalized summary."""
    template_replacements = {
        "{{DEVICE}}": summary["device"],
        "{{HOSTNAME}}": summary["hostname"],
        "{{IP_ADDRESS}}": summary["ip_address"],
        "{{OWNER}}": summary["owner"],
    }
    template_replacements.update(summary.get("template_replacements", {}))
    template_replacements.update(replacements)
    replace_text(workbook, template_replacements)

    persona_sheet = workbook["Persona Tracker"]
    for persona in summary["personas"]:
        row = find_row(persona_sheet, 1, persona["name"])
        if not row:
            continue
        persona_sheet.cell(row, 2, summary["owner"])
        persona_sheet.cell(row, 3, summary["host_os"])
        persona_sheet.cell(row, 4, summary["device_display"])
        set_status(persona_sheet.cell(row, 5), persona["status"])
        persona_sheet.cell(row, 6, persona["finding"])

    inventory_sheet = workbook["Device Inventory"]
    inventory_sheet.cell(2, 2, summary["device"])
    inventory_sheet.cell(2, 3, summary["initial_state"])
    inventory_sheet.cell(2, 4, summary["owner"])
    inventory_sheet.cell(2, 5, summary.get("inventory_status", "In Use"))

    app_sheet = workbook["App to Build"]
    for app in summary["apps"]:
        row = find_row(app_sheet, 2, app["name"])
        if not row:
            row = app_sheet.max_row + 1
            copy_row_style(app_sheet, row - 1, row, app_sheet.max_column)
            app_sheet.cell(row, 1, app.get("category", "Uncategorized"))
            app_sheet.cell(row, 2, app["name"])
        set_status(app_sheet.cell(row, 9), app["status"])
        app_sheet.cell(row, 10, summary["owner"])
        app_sheet.cell(row, 11, app["finding"])

    completed_sheet = workbook["Completed Apps"]
    template_completed_row = 2
    clear_rows(completed_sheet, 2, max(completed_sheet.max_row, 60), 6)
    completed_row = 2
    report_date = date.fromisoformat(summary["report_date"])
    for app in summary["apps"]:
        if app["status"] not in {"Completed", "User Completed"}:
            continue
        copy_row_style(completed_sheet, template_completed_row, completed_row, 6)
        completed_sheet.cell(completed_row, 1, app["name"])
        completed_sheet.cell(completed_row, 2, summary["owner"])
        completed_sheet.cell(completed_row, 3, app["persona"])
        completed_sheet.cell(completed_row, 4, summary["device_display"])
        completed_sheet.cell(completed_row, 5, report_date)
        completed_sheet.cell(completed_row, 5).number_format = "yyyy-mm-dd"
        completed_sheet.cell(completed_row, 6, app["finding"])
        completed_row += 1

    findings_sheet = workbook["Findings & Friction"]
    template_finding_row = 2
    clear_rows(findings_sheet, 2, max(findings_sheet.max_row, 30), 5)
    for index, finding in enumerate(summary["findings"], start=2):
        copy_row_style(findings_sheet, template_finding_row, index, 5)
        findings_sheet.cell(index, 1, finding["area"])
        findings_sheet.cell(index, 2, finding["severity"])
        findings_sheet.cell(index, 3, finding["description"])
        findings_sheet.cell(index, 4, finding["workaround"])
        findings_sheet.cell(index, 5, "")

    for sheet in workbook.worksheets:
        for row in sheet.iter_rows():
            for cell in row:
                alignment = copy.copy(cell.alignment)
                alignment.wrap_text = True
                alignment.vertical = "top"
                cell.alignment = alignment

    workbook.active = workbook.sheetnames.index("Persona Tracker")


def main() -> None:
    """Parse paths, populate a template copy, and save the output workbook."""
    parser = argparse.ArgumentParser(description="Create a QLI device dogfooding workbook.")
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--replace",
        action="append",
        default=[],
        metavar="OLD=NEW",
        help="Replace template-specific text; repeat for multiple values.",
    )
    args = parser.parse_args()

    summary = read_summary(args.summary)
    workbook = openpyxl.load_workbook(args.template)
    populate_workbook(workbook, summary, parse_replacements(args.replace))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(args.output)
    print(args.output)


if __name__ == "__main__":
    main()
