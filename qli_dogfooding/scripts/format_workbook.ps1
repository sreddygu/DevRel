param(
    [Parameter(Mandatory = $true)]
    [string]$InputPath,

    [Parameter(Mandatory = $true)]
    [string]$OutputPath
)

$ErrorActionPreference = "Stop"

function Get-OleColor {
    param([int]$Red, [int]$Green, [int]$Blue)
    return $Red + (256 * $Green) + (65536 * $Blue)
}

function Set-SheetLayout {
    param(
        $Sheet,
        [int[]]$Widths,
        [string]$FilterRange
    )

    $usedRange = $Sheet.UsedRange
    $usedRange.WrapText = $true
    $usedRange.VerticalAlignment = -4160
    $header = $Sheet.Range($FilterRange.Split(":")[0], $FilterRange.Split(":")[1]).Rows.Item(1)
    $header.Interior.Color = Get-OleColor 31 78 120
    $header.Font.Color = Get-OleColor 255 255 255
    $header.Font.Bold = $true
    $header.HorizontalAlignment = -4108
    $Sheet.Range($FilterRange).AutoFilter() | Out-Null

    for ($index = 0; $index -lt $Widths.Count; $index++) {
        $Sheet.Columns.Item($index + 1).ColumnWidth = $Widths[$index]
    }

    $Sheet.Activate()
    $Sheet.Application.ActiveWindow.SplitRow = 1
    $Sheet.Application.ActiveWindow.FreezePanes = $true
}

function Set-StatusColors {
    param($Range)
    $colors = @{
        "Completed" = @(198, 239, 206)
        "User Completed" = @(198, 224, 180)
        "Partial" = @(255, 235, 156)
        "Blocked" = @(255, 199, 206)
        "Not Tested" = @(217, 225, 242)
        "Not Applicable" = @(217, 217, 217)
    }
    foreach ($cell in $Range.Cells) {
        $value = [string]$cell.Value2
        if ($colors.ContainsKey($value)) {
            $rgb = $colors[$value]
            $cell.Interior.Color = Get-OleColor $rgb[0] $rgb[1] $rgb[2]
            $cell.Font.Bold = $true
        }
    }
}

$resolvedInput = (Resolve-Path $InputPath).Path
$resolvedOutput = if ([System.IO.Path]::IsPathRooted($OutputPath)) {
    [System.IO.Path]::GetFullPath($OutputPath)
}
else {
    [System.IO.Path]::GetFullPath((Join-Path (Get-Location).Path $OutputPath))
}
$outputDirectory = Split-Path $resolvedOutput -Parent
New-Item -ItemType Directory -Path $outputDirectory -Force | Out-Null
Copy-Item -LiteralPath $resolvedInput -Destination $resolvedOutput -Force

$excel = $null
$workbook = $null
try {
    $excel = New-Object -ComObject Excel.Application
    $excel.Visible = $false
    $excel.DisplayAlerts = $false
    $workbook = $excel.Workbooks.Open($resolvedOutput)

    Set-SheetLayout $workbook.Worksheets.Item("Persona Tracker") @(34, 16, 34, 24, 18, 70) "A1:F12"
    Set-SheetLayout $workbook.Worksheets.Item("Device Inventory") @(3, 18, 48, 18, 16, 78) "B1:F2"
    Set-SheetLayout $workbook.Worksheets.Item("App to Build") @(18, 34, 42, 38, 38, 20, 15, 28, 18, 16, 78, 26) "A1:L51"
    Set-SheetLayout $workbook.Worksheets.Item("Completed Apps") @(34, 16, 34, 24, 16, 80) "A1:F33"
    Set-SheetLayout $workbook.Worksheets.Item("Findings & Friction") @(22, 12, 78, 78, 24) "A1:E12"

    Set-StatusColors $workbook.Worksheets.Item("Persona Tracker").Range("E2:E12")
    Set-StatusColors $workbook.Worksheets.Item("App to Build").Range("I2:I51")

    $severityColors = @{
        "High" = @(255, 199, 206)
        "Medium" = @(255, 235, 156)
        "Low" = @(198, 239, 206)
    }
    foreach ($cell in $workbook.Worksheets.Item("Findings & Friction").Range("B2:B12").Cells) {
        $value = [string]$cell.Value2
        if ($severityColors.ContainsKey($value)) {
            $rgb = $severityColors[$value]
            $cell.Interior.Color = Get-OleColor $rgb[0] $rgb[1] $rgb[2]
            $cell.Font.Bold = $true
        }
    }

    $workbook.Worksheets.Item("Completed Apps").Range("E2:E33").NumberFormat = "yyyy-mm-dd"
    $workbook.Worksheets.Item("Persona Tracker").Activate()
    $workbook.Save()
    $workbook.Close($false)
}
finally {
    if ($workbook) {
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($workbook)
    }
    if ($excel) {
        $excel.Quit()
        [void][System.Runtime.InteropServices.Marshal]::ReleaseComObject($excel)
    }
    [GC]::Collect()
    [GC]::WaitForPendingFinalizers()
}

Write-Output $resolvedOutput
