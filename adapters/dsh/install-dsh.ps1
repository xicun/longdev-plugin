[CmdletBinding()]
param([string]$Project = (Get-Location).Path, [switch]$Check)
$ErrorActionPreference = 'Stop'
$installer = Join-Path $PSScriptRoot '../../scripts/install.py'
$arguments = @($installer, '--client', 'dsh', '--project', $Project)
if ($Check) { $arguments += '--check' }
if (Get-Command py -ErrorAction SilentlyContinue) {
    & py -3 @arguments
} else {
    & python3 @arguments
}
if ($LASTEXITCODE -ne 0) { throw "Longdev installation failed: $LASTEXITCODE" }
