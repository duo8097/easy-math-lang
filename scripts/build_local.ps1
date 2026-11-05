# Local test build of the Easy Math binaries (mirrors
# .github/workflows/build-installers.yml, minus Inno Setup).
#
# Usage (Windows, from the repo root):
#   powershell -ExecutionPolicy Bypass -File scripts/build_local.ps1 [-Jobs 2]
#
# Output: dist/easy-math-lang/ (shared onedir bundle: the easy-math-lang,
#        ezmath and easy-math-lsp executables plus the shared _internal/
#        directory), dist/easy-math-lang/easy-math-editor (editor).

param(
    [ValidateRange(1, 2147483647)]
    [int]$Jobs
)

$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)

# The PyInstaller flags live in one place (see scripts/build_binaries.py).
$buildArgs = @('--frozen', 'python', 'scripts/build_binaries.py')
if ($PSBoundParameters.ContainsKey('Jobs')) {
    $buildArgs += @('--jobs', "$Jobs")
}
uv run @buildArgs
if ($LASTEXITCODE -ne 0) { throw "build failed" }

Write-Host 'Build OK:'
Get-ChildItem -Path dist/easy-math-lang -Name | ForEach-Object { Write-Host "  $_" }
