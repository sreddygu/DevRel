param(
    [Parameter(Mandatory = $true)]
    [string]$SummaryPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath,

    [string]$ScreenshotDirectory
)

<#
.SYNOPSIS
Creates a device-specific QLI dogfooding Word report from normalized evidence.

.DESCRIPTION
Generates a reusable report containing device context, status totals, persona
coverage, all workflows present in the summary, friction findings, evidence
locations, and optional screenshots. The input JSON is produced by
build_qli_device_summary.py.
#>

$ErrorActionPreference = "Stop"
$wdCollapseEnd = 0
$wdFormatDocumentDefault = 16
$wdStyleNormal = -1
$wdStyleHeading1 = -2
$wdStyleHeading2 = -3
$wdStyleTitle = -63
$wdPageBreak = 7

$summary = Get-Content -LiteralPath (Resolve-Path $SummaryPath).Path -Raw | ConvertFrom-Json
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputPath)
$outputDirectory = Split-Path -Parent $resolvedOutput
if (-not (Test-Path $outputDirectory)) {
    New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
}

$word = $null
$document = $null

function Add-Paragraph {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Text,
        [int]$Style = $wdStyleNormal,
        [int]$SpaceAfter = 6
    )
    $range = $document.Content
    $range.Collapse($wdCollapseEnd)
    $range.Text = $Text
    $range.Style = $Style
    $range.ParagraphFormat.SpaceAfter = $SpaceAfter
    $range.InsertParagraphAfter()
}

function Add-Table {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Headers,
        [Parameter(Mandatory = $true)]
        [object[]]$Rows,
        [int[]]$Widths
    )
    $range = $document.Content
    $range.Collapse($wdCollapseEnd)
    $table = $document.Tables.Add($range, $Rows.Count + 1, $Headers.Count)
    $table.Style = "Table Grid"
    $table.AllowAutoFit = $true
    for ($column = 1; $column -le $Headers.Count; $column++) {
        $cell = $table.Cell(1, $column)
        $cell.Range.Text = [string]$Headers[$column - 1]
        $cell.Range.Bold = 1
        $cell.Shading.BackgroundPatternColor = 15128749
        if ($Widths -and $column -le $Widths.Count) {
            $cell.Width = $Widths[$column - 1]
        }
    }
    for ($row = 0; $row -lt $Rows.Count; $row++) {
        $values = @($Rows[$row])
        for ($column = 0; $column -lt $Headers.Count; $column++) {
            $table.Cell($row + 2, $column + 1).Range.Text = if ($column -lt $values.Count) {
                [string]$values[$column]
            } else {
                ""
            }
        }
    }
    $table.Range.Font.Size = 9
    $table.Range.ParagraphFormat.SpaceAfter = 0
    $end = $document.Content
    $end.Collapse($wdCollapseEnd)
    $end.InsertParagraphAfter()
}

function Add-PageBreak {
    $range = $document.Content
    $range.Collapse($wdCollapseEnd)
    $range.InsertBreak($wdPageBreak)
}

function Get-StatusCount {
    param([Parameter(Mandatory = $true)][string]$Name)
    if (-not $summary.status_counts) { return 0 }
    $property = $summary.status_counts.PSObject.Properties[$Name]
    if (-not $property) { return 0 }
    return [int]$property.Value
}

try {
    $word = New-Object -ComObject Word.Application
    $word.Visible = $false
    $word.DisplayAlerts = 0
    $document = $word.Documents.Add()

    $document.PageSetup.TopMargin = 50
    $document.PageSetup.BottomMargin = 50
    $document.PageSetup.LeftMargin = 55
    $document.PageSetup.RightMargin = 55

    $workflowCount = @($summary.apps).Count
    $completed = (Get-StatusCount -Name "Completed") + (Get-StatusCount -Name "User Completed")
    $partial = Get-StatusCount -Name "Partial"
    $blocked = Get-StatusCount -Name "Blocked"
    $notTested = Get-StatusCount -Name "Not Tested"
    $notApplicable = Get-StatusCount -Name "Not Applicable"
    $productName = if ($summary.qli_version -and $summary.qli_version -ne "Not reported") {
        "QLI $($summary.qli_version)"
    } else {
        "QLI"
    }

    Add-Paragraph -Text "$productName Dogfooding on $($summary.device)" -Style $wdStyleTitle -SpaceAfter 12
    Add-Paragraph -Text "$($summary.device_display) | $($summary.ip_address) | $($summary.report_date)" -SpaceAfter 18
    Add-Paragraph -Text "Evidence-based validation report generated from reusable QLI dogfooding tooling. Credentials are intentionally excluded." -SpaceAfter 12

    Add-Paragraph -Text "Executive Summary" -Style $wdStyleHeading1
    Add-Paragraph -Text "$completed of $workflowCount workflows were completed or user-completed. $partial were partial, $blocked blocked, $notTested not tested, and $notApplicable not applicable. These totals are derived from the normalized summary; consult the workflow table for the evidence supporting each status."
    if (@($summary.findings).Count -gt 0) {
        Add-Paragraph -Text "$(@($summary.findings).Count) findings or friction items require review before final readiness approval."
    } else {
        Add-Paragraph -Text "No findings were supplied. Confirm that this reflects an evidence review rather than missing assessment input."
    }

    Add-Paragraph -Text "Device and Session" -Style $wdStyleHeading1
    Add-Table -Headers @("Field", "Value") -Rows @(
        ,@("Device", $summary.device)
        ,@("Hostname", $summary.hostname)
        ,@("Active address", $summary.ip_address)
        ,@("QLI version", $summary.qli_version)
        ,@("Initial state", $summary.initial_state)
        ,@("Host environment", $summary.host_os)
        ,@("Owner", $summary.owner)
        ,@("Evidence captured", $summary.captured_at_utc)
    ) -Widths @(120, 380)

    Add-Paragraph -Text "Status Overview" -Style $wdStyleHeading1
    $statusRows = foreach ($property in $summary.status_counts.PSObject.Properties) {
        ,@($property.Name, $property.Value)
    }
    Add-Table -Headers @("Status", "Count") -Rows $statusRows -Widths @(250, 100)

    Add-Paragraph -Text "Persona Coverage" -Style $wdStyleHeading1
    $personaRows = foreach ($persona in $summary.personas) {
        ,@($persona.name, $persona.status, $persona.finding)
    }
    Add-Table -Headers @("Persona", "Status", "Finding") -Rows $personaRows -Widths @(130, 80, 300)

    Add-PageBreak
    Add-Paragraph -Text "Workflow Coverage" -Style $wdStyleHeading1
    Add-Paragraph -Text "The following table records all $workflowCount workflows in the normalized summary. Statuses reflect baseline inference or explicit verified-result overrides rather than copied results from another target."
    $appRows = foreach ($app in $summary.apps) {
        ,@($app.name, $app.status, $app.persona, $app.finding)
    }
    Add-Table -Headers @("Workflow", "Status", "Persona", "Evidence / Finding") -Rows $appRows -Widths @(120, 70, 95, 235)

    Add-PageBreak
    Add-Paragraph -Text "Findings and Friction" -Style $wdStyleHeading1
    $findingRows = if (@($summary.findings).Count -gt 0) {
        foreach ($finding in $summary.findings) {
            ,@($finding.area, $finding.severity, $finding.description, $finding.workaround)
        }
    } else {
        ,@("Assessment", "Informational", "No findings were supplied in the normalized summary.", "Review workflow evidence and add verified friction items when applicable.")
    }
    Add-Table -Headers @("Area", "Severity", "Description", "Recommended Action") -Rows $findingRows -Widths @(75, 55, 190, 190)

    Add-Paragraph -Text "Evidence Inventory" -Style $wdStyleHeading1
    $artifactRows = @()
    if ($summary.evidence -and $summary.evidence.artifacts) {
        $artifactRows = foreach ($artifact in $summary.evidence.artifacts) {
            ,@($artifact.artifact, $artifact.purpose)
        }
    }
    if (@($artifactRows).Count -eq 0) {
        $artifactRows = @(,@("No artifacts listed", "Add reviewed evidence artifacts to the assessment-results JSON."))
    }
    Add-Table -Headers @("Artifact", "Purpose") -Rows $artifactRows -Widths @(220, 300)

    if ($ScreenshotDirectory -and (Test-Path $ScreenshotDirectory)) {
        $screenshots = Get-ChildItem -LiteralPath $ScreenshotDirectory -File | Where-Object {
            $_.Extension -in @(".png", ".jpg", ".jpeg")
        } | Sort-Object Name
        if ($screenshots.Count -gt 0) {
            Add-PageBreak
            Add-Paragraph -Text "Supporting Screenshots" -Style $wdStyleHeading1
            foreach ($screenshot in $screenshots) {
                Add-Paragraph -Text $screenshot.BaseName -Style $wdStyleHeading2
                $range = $document.Content
                $range.Collapse($wdCollapseEnd)
                $picture = $document.InlineShapes.AddPicture($screenshot.FullName, $false, $true, $range)
                if ($picture.Width -gt 470) {
                    $scale = 470 / $picture.Width
                    $picture.Width = 470
                    $picture.Height = $picture.Height * $scale
                }
                $end = $document.Content
                $end.Collapse($wdCollapseEnd)
                $end.InsertParagraphAfter()
            }
        }
    }

    Add-Paragraph -Text "Conclusion" -Style $wdStyleHeading1
    Add-Paragraph -Text "The assessment of $($summary.device) recorded $completed completed or user-completed workflows out of $workflowCount, with $partial partial, $blocked blocked, $notTested not tested, and $notApplicable not applicable. Readiness decisions should use the per-workflow evidence and findings in this report; untested or blocked activities must not be treated as verified capabilities."

    foreach ($section in $document.Sections) {
        $footer = $section.Footers.Item(1).Range
        $footer.Text = "$productName Dogfooding on $($summary.device) | $($summary.report_date)"
        $footer.Font.Size = 8
        $footer.ParagraphFormat.Alignment = 1
    }

    $document.SaveAs2($resolvedOutput, $wdFormatDocumentDefault)
    $document.Close($false)
    $document = $null
} finally {
    if ($document) { $document.Close($false) }
    if ($word) { $word.Quit() }
    if ($document) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($document) }
    if ($word) { [void][Runtime.InteropServices.Marshal]::ReleaseComObject($word) }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

Write-Output $resolvedOutput
