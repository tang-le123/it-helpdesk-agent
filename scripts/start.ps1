param(
  [int]$ApiPort = 8002,
  [int]$WebPort = 5173,
  [switch]$WithModels,
  [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
  throw "Missing .venv. Create it first: python -m venv --system-site-packages .venv; .venv\Scripts\python -m pip install -e . --no-deps"
}

# Demo mode by default: hash embeddings + lexical rerank, no model download.
# Use -WithModels for real bge weights (about 95MB on first run).
if ($WithModels) {
  $env:LOCAL_EMBEDDING_ENABLED = "true"
  $env:CROSS_ENCODER_ENABLED = "true"
  $env:HF_ENDPOINT = "https://hf-mirror.com"
} else {
  $env:LOCAL_EMBEDDING_ENABLED = "false"
  $env:CROSS_ENCODER_ENABLED = "false"
}
$env:UNSTRUCTURED_ENABLED = "false"

$webDir = Join-Path $root "frontend"
if (-not (Test-Path (Join-Path $webDir "node_modules"))) {
  Write-Host "First run: installing frontend dependencies (npm ci) ..." -ForegroundColor Cyan
  Push-Location $webDir
  & npm.cmd ci --no-audit --no-fund
  Pop-Location
}

Write-Host "Starting API on http://127.0.0.1:$ApiPort" -ForegroundColor Green
Start-Process -FilePath $python `
  -ArgumentList "-m", "uvicorn", "app.asgi:app", "--host", "127.0.0.1", "--port", "$ApiPort", "--reload" `
  -WorkingDirectory $root | Out-Null

Write-Host "Starting Web on http://127.0.0.1:$WebPort" -ForegroundColor Green
Start-Process -FilePath "npm.cmd" `
  -ArgumentList "run", "dev", "--", "--host", "127.0.0.1", "--port", "$WebPort" `
  -WorkingDirectory $webDir | Out-Null

$ready = $false
for ($i = 0; $i -lt 80; $i++) {
  Start-Sleep -Milliseconds 500
  try {
    Invoke-RestMethod "http://127.0.0.1:$ApiPort/api/v1/health" -TimeoutSec 2 | Out-Null
    $ready = $true
    break
  } catch { }
}

if ($ready) {
  Write-Host "API is ready." -ForegroundColor Green
} else {
  Write-Host "API did not become ready in 40s. Check the API window logs." -ForegroundColor Yellow
}

if (-not $NoBrowser) {
  Start-Process "http://127.0.0.1:$WebPort"
}

Write-Host ""
Write-Host "API docs: http://127.0.0.1:$ApiPort/docs"
Write-Host "Stop:     stop.bat"
