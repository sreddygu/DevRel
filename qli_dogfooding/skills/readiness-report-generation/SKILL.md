# Readiness Report Generation

Create deliverables only from verified evidence and approved output paths.

1. Build the normalized summary with `scripts/build_qli_device_summary.py`.
2. Generate the workbook with `scripts/create_qli_device_workbook.py`.
3. Generate the report with `scripts/create_qli_device_report.ps1`.
4. Format the workbook with `scripts/format_workbook.ps1` only when requested.
5. Reconcile status totals, completed records, findings, device identifiers, and
   report prose before delivery.

Request approval before overwriting an existing workbook or report. Do not infer
completion from a generated document; report status must trace to verified
evidence.
