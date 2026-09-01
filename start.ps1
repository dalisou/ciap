param(
    [int]$Port = 8000
)

$ErrorActionPreference = 'Stop'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

$existing = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
if ($existing) {
    Write-Host "A porta $Port ja esta em uso." -ForegroundColor Red
    $pids = $existing | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($processId in $pids) {
        $proc = Get-Process -Id $processId -ErrorAction SilentlyContinue
        if ($proc) {
            Write-Host "PID $($proc.Id) - $($proc.ProcessName)" -ForegroundColor Yellow
        }
    }
    Write-Host "" 
    Write-Host "Use outra porta:" -ForegroundColor Cyan
    Write-Host "  .\start.ps1 -Port 8001" -ForegroundColor Cyan
    exit 1
}

$pythonCmd = Get-Command py -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
}

if (-not $pythonCmd) {
    Write-Host "Python nao foi encontrado no PATH. Instale o Python 3 e tente novamente." -ForegroundColor Red
    exit 1
}

Write-Host "Iniciando CIAP-PB na porta $Port..." -ForegroundColor Green
$env:PORT = [string]$Port
& $pythonCmd.Source app.py
