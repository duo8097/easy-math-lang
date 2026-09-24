# Local test build of the Easy Math binaries (mirrors
# .github/workflows/build-windows-installer.yml, minus Inno Setup).
#
# Usage (Windows, from the repo root):
#   powershell -ExecutionPolicy Bypass -File scripts/build_local.ps1
#
# Output: dist/easy-math-lang.exe, dist/easy-math-lsp.exe,
#         dist/easy-math-editor/easy-math-editor.exe

$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)

@(
    @('entry_compiler.py', 'from compiler import main', 'main()'),
    @('entry_lsp.py', 'from lsp.server import main', 'main()'),
    @('entry_editor.py', 'from editor.app import main', 'main()')
) | ForEach-Object {
    $file, $importLine, $call = $_
    Set-Content -Path $file -Value "$importLine`r`nif __name__ == '__main__':`r`n    $call`r`n" -Encoding Ascii
}

try {
    uv run pyinstaller entry_compiler.py --name easy-math-lang --onefile `
        --collect-all typst --collect-all numpy --noconfirm
    if ($LASTEXITCODE -ne 0) { throw "compiler build failed" }

    uv run pyinstaller entry_lsp.py --name easy-math-lsp --onefile `
        --collect-all pygls --collect-all typst --noconfirm
    if ($LASTEXITCODE -ne 0) { throw "lsp build failed" }

    uv run pyinstaller entry_editor.py --name easy-math-editor --onedir `
        --windowed --collect-all PySide6 --collect-all typst --noconfirm
    if ($LASTEXITCODE -ne 0) { throw "editor build failed" }
}
finally {
    Remove-Item entry_compiler.py, entry_lsp.py, entry_editor.py -ErrorAction SilentlyContinue
}

Write-Host 'Build OK:'
Get-ChildItem dist/easy-math-lang.exe, dist/easy-math-lsp.exe, dist/easy-math-editor/easy-math-editor.exe
