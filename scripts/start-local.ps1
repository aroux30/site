# start-local.ps1 — ensures the local e-commerce stack (backend API + frontend) is running.
# Used by the scheduled task "EcommerceLocalStack" (runs at logon) or manually.
$ErrorActionPreference = "SilentlyContinue"

$root    = Split-Path -Parent $PSScriptRoot   # repo root (scripts/..)
$logDir  = Join-Path $root "logs"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

function Test-Port([int]$Port) {
    $c = New-Object Net.Sockets.TcpClient
    try { $c.Connect("127.0.0.1", $Port); return $c.Connected } finally { $c.Close() }
}

# ── Backend (FastAPI + uvicorn on :8000) ─────────────────────────────
if (-not (Test-Port 8000)) {
    $env:DATABASE_URL        = "postgresql+asyncpg://ecommerce:ecommerce_dev_password@127.0.0.1:5432/ecommerce"
    $env:ENVIRONMENT         = "development"
    $env:DEBUG               = "true"
    $env:ENABLE_ELASTICSEARCH = "false"
    $env:ENABLE_CELERY       = "false"
    $py = (Get-Command python -ErrorAction SilentlyContinue).Source
    if (-not $py) { $py = "python" }
    Start-Process -FilePath $py `
        -ArgumentList "-m","uvicorn","app.main:app","--host","127.0.0.1","--port","8000" `
        -WorkingDirectory (Join-Path $root "backend") -WindowStyle Hidden `
        -RedirectStandardOutput (Join-Path $logDir "backend_local.log") `
        -RedirectStandardError  (Join-Path $logDir "backend_local.err.log")
}

# ── Frontend (Next.js on :3000) ──────────────────────────────────────
if (-not (Test-Port 3000)) {
    $npm = "C:\Program Files\nodejs\npm.cmd"
    if (-not (Test-Path $npm)) { $npm = "npm" }
    Start-Process -FilePath "cmd.exe" `
        -ArgumentList "/c","`"$npm`" start" `
        -WorkingDirectory (Join-Path $root "frontend") -WindowStyle Hidden
}
