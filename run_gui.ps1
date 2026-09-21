param(
    [ValidateRange(1024, 65535)]
    [int]$Port = 8501,
    [switch]$Headless,
    [switch]$BuildOnly
)

$ErrorActionPreference = 'Stop'
$python = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$build = Join-Path $PSScriptRoot '.gui-build'
$targets = @(
    @{ Name = 'mc_gui'; Sources = @('mc_gui.cpp', 'bsm.cpp'); Headers = @('bsm.hpp', 'gui_common.hpp') },
    @{ Name = 'pricing_gui'; Sources = @('pricing_gui.cpp', 'bsm.cpp', 'bino.cpp'); Headers = @('bsm.hpp', 'bino.hpp', 'gui_common.hpp') },
    @{ Name = 'ppn_gui'; Sources = @('ppn_gui.cpp'); Headers = @('gui_common.hpp') }
)

foreach ($target in $targets) {
    $engine = Join-Path $build "$($target.Name).exe"
    $sources = @($target.Sources | ForEach-Object { Join-Path $PSScriptRoot $_ })
    $dependencies = @($target.Sources + $target.Headers | ForEach-Object { Join-Path $PSScriptRoot $_ })
    $dependencies += $PSCommandPath
    $newest = ($dependencies | Get-Item | Measure-Object -Property LastWriteTimeUtc -Maximum).Maximum
    if (-not (Test-Path -LiteralPath $engine) -or $newest -gt (Get-Item -LiteralPath $engine).LastWriteTimeUtc) {
        $compiler = Get-Command clang++ -ErrorAction SilentlyContinue
        $clang = if ($compiler) { $compiler.Source } else { 'C:\Program Files\LLVM\bin\clang++.exe' }
        if (-not (Test-Path -LiteralPath $clang)) {
            throw 'clang++ was not found. Install LLVM or add its bin directory to PATH.'
        }
        New-Item -ItemType Directory -Force -Path $build | Out-Null
        & $clang -std=c++20 -O2 -Wall -Wextra -Werror -DPRICERS_NO_MAIN @sources -o $engine
        if ($LASTEXITCODE -ne 0) { throw "C++ build failed for $($target.Name)." }
    }
}
if ($BuildOnly) { return }
if (-not (Test-Path -LiteralPath $python)) {
    throw 'Create the GUI environment first: uv venv --python 3.12 .venv; .\.venv\Scripts\python.exe -m ensurepip; .\.venv\Scripts\python.exe -m pip install -r requirements-gui.txt'
}

& $python -m streamlit run (Join-Path $PSScriptRoot 'gui.py') `
    --server.address 127.0.0.1 --server.port $Port `
    --server.headless $Headless.IsPresent.ToString().ToLowerInvariant() `
    --browser.gatherUsageStats false
if ($LASTEXITCODE -ne 0) { throw 'GUI server stopped with an error.' }
