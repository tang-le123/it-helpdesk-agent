param(
  [int]$ApiPort = 8002,
  [int]$FrontendPort = 5173,
  [string]$Python = "python"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

if (-not (Test-Path "frontend\node_modules")) {
  throw "未找到 frontend/node_modules，请先在 frontend 目录运行 npm ci。"
}

# Demo mode: hash embeddings + lexical rerank, no model download.
$env:LOCAL_EMBEDDING_ENABLED = "false"
$env:CROSS_ENCODER_ENABLED = "false"
$env:UNSTRUCTURED_ENABLED = "false"

Start-Process -FilePath $Python `
  -ArgumentList "-m", "uvicorn", "app.asgi:app", "--host", "127.0.0.1", "--port", "$ApiPort" `
  -WorkingDirectory $root

Start-Process -FilePath "frontend\node_modules\.bin\vite.cmd" `
  -ArgumentList "--host", "127.0.0.1", "--port", "$FrontendPort" `
  -WorkingDirectory (Join-Path $root "frontend")

Write-Host "API:      http://127.0.0.1:$ApiPort"
Write-Host "Frontend: http://127.0.0.1:$FrontendPort"
