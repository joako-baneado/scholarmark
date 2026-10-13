#Requires -Version 5.1
<#
.SYNOPSIS
    Aprovisiona el entorno virtual aislado ScholarMark/.venv con soporte ONNX Runtime (DirectML / CPU) y herramientas de benchmark.
#>
param(
    [switch]$WithDirectML = $true,
    [switch]$Recreate = $false
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPath = Join-Path $RepoRoot ".venv"

Write-Host "==> Configuring ScholarMark v3.0 Environment at: $VenvPath" -ForegroundColor Cyan

if ($Recreate -and (Test-Path $VenvPath)) {
    Write-Host "Removing existing .venv..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $VenvPath
}

if (-not (Test-Path $VenvPath)) {
    python -m venv $VenvPath --system-site-packages
}

$VenvPython = Join-Path $VenvPath "Scripts\python.exe"

& $VenvPython -m pip install --upgrade pip --quiet
& $VenvPython -m pip install -e "$RepoRoot[dev,bench]" --quiet

if ($WithDirectML) {
    Write-Host "Checking DirectML provider availability..." -ForegroundColor Cyan
    try {
        & $VenvPython -m pip install onnxruntime-directml --quiet
    } catch {
        Write-Host "Warning: onnxruntime-directml installation skipped, falling back to CPUExecutionProvider." -ForegroundColor Yellow
    }
}

& $VenvPython -c "import scholarmark, onnxruntime as ort; print('ScholarMark:', scholarmark.__version__); print('ORT Providers:', ort.get_available_providers())"
Write-Host "==> Environment ready!" -ForegroundColor Green
