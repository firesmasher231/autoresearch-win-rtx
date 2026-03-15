# Build, launch, and attach to the auto-ornithopter Docker container.
#
# Usage:
#   .\launch.ps1              # build + start + attach
#   .\launch.ps1 -NoBuild     # start + attach (skip rebuild)
#   .\launch.ps1 -Detached    # build + start in background (no attach)

param(
    [switch]$NoBuild,
    [switch]$Detached
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $ScriptDir

try {
    if (-not $NoBuild) {
        Write-Host "=== Building image ===" -ForegroundColor Cyan
        docker compose build
        if ($LASTEXITCODE -ne 0) { Write-Error "Build failed"; exit 1 }
    }

    # Stop old container if running
    $running = docker ps -q -f name=auto-ornithopter 2>$null
    if ($running) {
        Write-Host "=== Stopping old container ===" -ForegroundColor Yellow
        docker stop auto-ornithopter | Out-Null
        docker rm auto-ornithopter | Out-Null
    } else {
        # Remove stopped container if exists
        docker rm auto-ornithopter 2>$null | Out-Null
    }

    Write-Host "=== Starting container ===" -ForegroundColor Cyan
    docker compose up -d
    if ($LASTEXITCODE -ne 0) { Write-Error "Failed to start container"; exit 1 }

    if ($Detached) {
        Write-Host "`nContainer running in background." -ForegroundColor Green
        Write-Host "  Attach later:  docker attach auto-ornithopter"
        Write-Host "  View logs:     docker logs -f auto-ornithopter"
        Write-Host "  Pull results:  .\pull_and_record.ps1"
    } else {
        Write-Host "`n=== Attaching to Claude Code ===" -ForegroundColor Cyan
        Write-Host "  Detach without killing: Ctrl+P, Ctrl+Q" -ForegroundColor Yellow
        Write-Host "  (Ctrl+C will kill the session!)" -ForegroundColor Red
        Write-Host ""
        docker attach auto-ornithopter
    }
} finally {
    Pop-Location
}
