# ==============================================================================
# scripts/loop/rebuild-and-verify.ps1
# Self-healing loop: Safe Next.js rebuild, port recycling, and BUILD_ID verification
# ==============================================================================

param (
    [int]$Port = 3000,
    [int]$MaxRetries = 5,
    [int]$HealthTimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Resolve-Path (Join-Path $ScriptDir "..\..")
$FrontendDir = Join-Path $ProjectRoot "frontend"
$NextDir = Join-Path $FrontendDir ".next"
$BuildIdFile = Join-Path $NextDir "BUILD_ID"

Write-Host ">>> [rebuild-and-verify] Starting rebuild verification on port $Port..." -ForegroundColor Cyan

# 1. Stop any process listening on the target port
Write-Host ">>> [1/5] Stopping any process on port $Port..." -ForegroundColor Yellow
try {
    $connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    if ($connections) {
        $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($procId in $pids) {
            if ($procId -gt 4) {
                Write-Host "    Killing process tree $procId on port $Port..."
                cmd /c "taskkill /F /T /PID $procId" 2>$null
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            }
        }
        Start-Sleep -Seconds 1
    }
} catch {
    # Fallback to netstat if Get-NetTCPConnection fails
    $lines = netstat -ano | Select-String ":$Port\s+.*LISTENING\s+(\d+)"
    foreach ($line in $lines) {
        if ($line.Matches.Groups.Count -gt 1) {
            $procId = [int]$line.Matches.Groups[1].Value
            if ($procId -gt 4) {
                Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            }
        }
    }
}

# 2. Safely remove .next with retry loop (Windows file locks)
Write-Host ">>> [2/5] Cleaning .next cache directory..." -ForegroundColor Yellow
if (Test-Path $NextDir) {
    $deleted = $false
    for ($i = 1; $i -le $MaxRetries; $i++) {
        try {
            Remove-Item -Path $NextDir -Recurse -Force -ErrorAction Stop
            $deleted = $true
            Write-Host "    Successfully removed .next directory (attempt $i)." -ForegroundColor Green
            break
        } catch {
            Write-Warning "    Attempt $i to remove .next failed (locked). Retrying in 1s..."
            Start-Sleep -Seconds 1
        }
    }
    if (-not $deleted) {
        throw "Failed to delete $NextDir after $MaxRetries attempts due to file locks."
    }
} else {
    Write-Host "    .next directory does not exist. Skipping removal."
}

# 3. Build frontend
Write-Host ">>> [3/5] Executing npm run build..." -ForegroundColor Yellow
Push-Location $FrontendDir
try {
    & npm run build
    if ($LASTEXITCODE -ne 0) {
        throw "npm run build failed with exit code $LASTEXITCODE"
    }
} finally {
    Pop-Location
}

if (-not (Test-Path $BuildIdFile)) {
    throw "BUILD_ID file was not generated at $BuildIdFile"
}
$ExpectedBuildId = (Get-Content $BuildIdFile -Raw).Trim()
Write-Host "    Generated BUILD_ID: $ExpectedBuildId" -ForegroundColor Green

# 4. Start next in production mode on target port
Write-Host ">>> [4/5] Launching next start on port $Port in background..." -ForegroundColor Yellow
$StartProcess = Start-Process -FilePath "cmd.exe" -ArgumentList "/c npm run start -- -p $Port" -WorkingDirectory $FrontendDir -PassThru -WindowStyle Hidden

Write-Host "    Spawned Next.js server with PID $($StartProcess.Id)."

# 5. Poll /api/health until healthy and BUILD_ID matches
Write-Host ">>> [5/5] Polling /api/health for verification..." -ForegroundColor Yellow
$HealthUrl = "http://127.0.0.1:$Port/api/health"
$Stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$Verified = $false

while ($Stopwatch.Elapsed.TotalSeconds -lt $HealthTimeoutSeconds) {
    try {
        $response = Invoke-RestMethod -Uri $HealthUrl -Method Get -TimeoutSec 3 -ErrorAction Stop
        if ($response -and $response.buildId) {
            $ActualBuildId = $response.buildId.Trim()
            if ($ActualBuildId -eq $ExpectedBuildId) {
                Write-Host ">>> [SUCCESS] Server is LIVE and verified!" -ForegroundColor Green
                Write-Host "    Health Status : $($response.status)"
                Write-Host "    Expected ID   : $ExpectedBuildId"
                Write-Host "    Actual ID     : $ActualBuildId"
                Write-Host "    Backend Reach : $($response.backend.ok) (HTTP $($response.backend.statusCode))"
                $Verified = $true
                break
            } else {
                Write-Warning "    Build ID mismatch: Expected $ExpectedBuildId, got $ActualBuildId. Waiting..."
            }
        }
    } catch {
        # Server still booting up
    }
    Start-Sleep -Milliseconds 800
}

if (-not $Verified) {
    throw "Verification failed: Server at $HealthUrl did not report matching BUILD_ID ($ExpectedBuildId) within $HealthTimeoutSeconds seconds."
}

Write-Host ">>> Rebuild and verification completed successfully in $([math]::Round($Stopwatch.Elapsed.TotalSeconds, 1))s." -ForegroundColor Green
exit 0
