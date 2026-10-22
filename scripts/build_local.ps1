# Local test build of the Easy Math binaries (mirrors
# .github/workflows/build-installers.yml, minus Inno Setup).
#
# Usage (Windows, from the repo root):
#   powershell -ExecutionPolicy Bypass -File scripts/build_local.ps1 [-Jobs 2]
#
# Output: dist/easy-math-lang.exe, dist/ezmath.exe (alias copy),
#         dist/easy-math-lsp.exe, dist/easy-math-editor/easy-math-editor.exe

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
Get-ChildItem dist/easy-math-lang.exe, dist/ezmath.exe, dist/easy-math-lsp.exe, dist/easy-math-editor/easy-math-editor.exe
