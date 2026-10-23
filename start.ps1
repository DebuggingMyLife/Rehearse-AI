# Launch the Retake backend (FastAPI on :8000) and frontend (Vite on :5173).
# Usage: .\start.ps1 [-Reload]
param([switch]$Reload)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot
$py = Join-Path $root "backend\.venv\Scripts\python.exe"

if (-not (Test-Path $py)) {
    Write-Host "Backend venv not found. See README: Setup -> Backend." -ForegroundColor Red
    exit 1
}
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) {
    Write-Host "npm not found. Install Node.js 20+ (see README)." -ForegroundColor Red
    Write-Host "If you just installed it, open a new terminal so PATH is refreshed." -ForegroundColor Red
    exit 1
}
# npm writes warnings to stderr; don't let PowerShell treat those as fatal.
$ErrorActionPreference = "Continue"
if (-not (Test-Path (Join-Path $root ".env"))) {
    Copy-Item (Join-Path $root ".env.example") (Join-Path $root ".env")
    Write-Host "Created .env from .env.example" -ForegroundColor Yellow
}
if (-not (Test-Path (Join-Path $root "frontend\node_modules"))) {
    Push-Location (Join-Path $root "frontend"); npm install; $npmExit = $LASTEXITCODE; Pop-Location
    if ($npmExit -ne 0) { Write-Host "npm install failed." -ForegroundColor Red; exit 1 }
}

$uvArgs = @("-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--timeout-graceful-shutdown", "3")
if ($Reload) { $uvArgs += "--reload" }
$backend = Start-Process -FilePath $py -ArgumentList $uvArgs `
    -WorkingDirectory (Join-Path $root "backend") -NoNewWindow -PassThru

try {
    Write-Host "Backend PID $($backend.Id). Open http://localhost:5173" -ForegroundColor Green
    Push-Location (Join-Path $root "frontend")
    npm run dev
}
finally {
    Pop-Location
    # /T kills uvicorn's reload/worker children too
    taskkill /PID $backend.Id /T /F | Out-Null
}
