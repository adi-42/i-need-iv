param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8501,
    [switch]$Headless,
    [switch]$BuildOnly
)

$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$source = Join-Path $PSScriptRoot 'mc_gui.cpp'
$build = Join-Path $PSScriptRoot '.gui-build'
$engine = Join-Path $build 'mc_gui.exe'

if (-not (Test-Path -LiteralPath $engine) -or
    (Get-Item -LiteralPath $source).LastWriteTimeUtc -gt (Get-Item -LiteralPath $engine).LastWriteTimeUtc) {
    $compiler = Get-Command clang++ -ErrorAction SilentlyContinue
    $clang = if ($compiler) { $compiler.Source } else { 'C:\Program Files\LLVM\bin\clang++.exe' }
    if (-not (Test-Path -LiteralPath $clang)) {
        throw 'clang++ was not found. Install LLVM or add its bin directory to PATH.'
    }
    New-Item -ItemType Directory -Force -Path $build | Out-Null
    & $clang -std=c++20 -O2 -Wall -Wextra -Werror $source -o $engine
    if ($LASTEXITCODE -ne 0) { throw 'C++ build failed.' }
}
if ($BuildOnly) { return }
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Create the GUI environment first: uv venv --python 3.12 .venv; uv pip install --python .venv\Scripts\python.exe -r requirements-gui.txt'
}

& $python -m streamlit run (Join-Path $PSScriptRoot 'gui.py') `
    --server.address 127.0.0.1 --server.port $Port `
    --server.headless $Headless.IsPresent.ToString().ToLowerInvariant() `
    --browser.gatherUsageStats false
if ($LASTEXITCODE -ne 0) { throw 'GUI server stopped with an error.' }
