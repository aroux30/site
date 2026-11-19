# ==============================================================================
# .claude/hooks/loop-guard.ps1
# PreToolUse security hook protecting loop invariants and critical files
# ==============================================================================

$ErrorActionPreference = "SilentlyContinue"

# Check for emergency stop flag file
$StopFlag = Join-Path $PSScriptRoot "..\..\.loop\AGENT_STOP"
if (Test-Path $StopFlag) {
    [Console]::Error.WriteLine("CRITICAL: AGENT_STOP flag is present at $StopFlag. Execution halted by loop guard.")
    exit 2
}

# Read stdin JSON payload from Claude Code
$rawInput = [Console]::In.ReadToEnd()
if (-not $rawInput) {
    exit 0
}

try {
    $payload = $rawInput | ConvertFrom-Json
} catch {
    exit 0
}

$toolName = $payload.tool_name
$toolInput = $payload.tool_input

# 1. Guard against file modification tools (Write, Edit)
if ($toolName -in @("Write", "Edit")) {
    $filePath = ""
    if ($toolInput.file_path) {
        $filePath = $toolInput.file_path.ToString().Replace("\", "/")
    }

    # Protected paths
    $protectedPatterns = @(
        "backend/app/modules/audit/application/audit_service.py",
        "audit_service.py",
        ".loop/audits/",
        ".loop/artifacts/",
        ".loop/contract.json"
    )

    foreach ($pat in $protectedPatterns) {
        if ($filePath -like "*$pat*") {
            [Console]::Error.WriteLine("SECURITY REJECTED: Modification of '$filePath' is prohibited by loop-guard invariant: $pat")
            exit 1
        }
    }
}

# 2. Guard against destructive git commands via Bash tool
if ($toolName -eq "Bash") {
    $command = ""
    if ($toolInput.command) {
        $command = $toolInput.command.ToString()
    }

    $forbiddenPatterns = @(
        "git\s+reset\s+--hard",
        "git\s+clean\s+-f",
        "git\s+push\s+.*--force",
        "git\s+push\s+-f",
        "git\s+checkout\s+main",
        "git\s+switch\s+main",
        "git\s+merge.*main"
    )

    foreach ($regex in $forbiddenPatterns) {
        if ($command -match $regex) {
            [Console]::Error.WriteLine("SECURITY REJECTED: Destructive or forbidden git command: '$command'")
            exit 1
        }
    }

    # Prohibit deleting artifacts or audit directory via rm / del
    if ($command -match "rm\s+.*\.loop/(artifacts|audits)" -or $command -match "Remove-Item.*\.loop\\(artifacts|audits)") {
        [Console]::Error.WriteLine("SECURITY REJECTED: Deleting loop artifacts or audits is prohibited.")
        exit 1
    }
}

exit 0
