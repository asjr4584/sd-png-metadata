<#
.SYNOPSIS
Packages the WordPress plugin sd-png-metadata-v1 into a distributable ZIP archive.

.DESCRIPTION
Validates required runtime files and compresses wp-plugin/sd-png-metadata-v1 into a clean ZIP file suitable for WordPress plugin installation.
#>

[CmdletBinding()]
param(
    [string]$OutputDir = "",
    [switch]$Force
)

$ErrorActionPreference = 'Stop'

$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
if (-not $OutputDir) {
    $OutputDir = $RepoRoot
} else {
    $OutputDir = [System.IO.Path]::GetFullPath($OutputDir)
}

$PluginSrc = Join-Path $RepoRoot "wp-plugin\sd-png-metadata-v1"
$MainPhp = Join-Path $PluginSrc "sd-png-metadata-v1.php"

if (-not (Test-Path $MainPhp)) {
    Write-Error "Main plugin file not found: $MainPhp"
    exit 1
}

# Extract version from plugin header
$Version = "1.0.0"
$Content = Get-Content $MainPhp -Raw
if ($Content -match 'Version:\s*([^\r\n]+)') {
    $Version = $Matches[1].Trim()
}

$ZipName = "sd-png-metadata-v1.zip"
$ZipPath = Join-Path $OutputDir $ZipName

Write-Host "Packaging sd-png-metadata plugin v$Version..." -ForegroundColor Cyan
Write-Host "Source: $PluginSrc" -ForegroundColor Gray
Write-Host "Destination: $ZipPath" -ForegroundColor Gray

if (Test-Path $ZipPath) {
    Remove-Item $ZipPath -Force
}

# Ensure destination directory exists
$TargetDir = Split-Path $ZipPath -Parent
if (-not (Test-Path $TargetDir)) {
    New-Item -ItemType Directory -Path $TargetDir -Force | Out-Null
}

# Compress-Archive
Compress-Archive -Path $PluginSrc -DestinationPath $ZipPath -CompressionLevel Optimal

if (Test-Path $ZipPath) {
    $Item = Get-Item $ZipPath
    $SizeMB = [math]::Round($Item.Length / 1MB, 2)
    Write-Host "[OK] Packaged $ZipName ($SizeMB MB) successfully." -ForegroundColor Green
} else {
    Write-Error "Failed to generate $ZipPath"
    exit 1
}
