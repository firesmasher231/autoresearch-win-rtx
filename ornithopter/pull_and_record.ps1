# Pull latest design from running Docker container and record MP4 visualization.
#
# Usage:
#   .\pull_and_record.ps1                    # default output: docker_latest.mp4
#   .\pull_and_record.ps1 my_run.mp4         # custom output filename
#   .\pull_and_record.ps1 -NoRecord          # just pull files, skip recording

param(
    [string]$Output = "docker_latest.mp4",
    [switch]$NoRecord
)

$ErrorActionPreference = "Stop"
$Container = "auto-ornithopter"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

# Find docker
$Docker = "docker"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    $DockerPath = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    if (Test-Path $DockerPath) {
        $Docker = $DockerPath
    } else {
        Write-Error "docker not found"
        exit 1
    }
}

# Check container is running
$running = & $Docker ps --format '{{.Names}}' 2>&1
if ($running -notcontains $Container) {
    Write-Error "Container '$Container' is not running. Start with: docker compose up -d"
    exit 1
}

Write-Host "=== Pulling files from $Container ===" -ForegroundColor Cyan

& $Docker cp "${Container}:/app/design.py" "$ScriptDir\design_docker.py"
& $Docker cp "${Container}:/app/results.tsv" "$ScriptDir\results_docker.tsv" 2>$null
& $Docker cp "${Container}:/app/sim_output.json" "$ScriptDir\sim_output_docker.json" 2>$null

Write-Host ""
Write-Host "=== Docker agent's current design ===" -ForegroundColor Cyan
Select-String -Path "$ScriptDir\design_docker.py" -Pattern "^(SEMI_SPAN|ROOT_CHORD|TAPER_RATIO|FLAP_FREQUENCY|FLAP_AMPLITUDE|PITCH_AMPLITUDE|PHASE_OFFSET|MEAN_AOA|FLIGHT_SPEED|DIHEDRAL_ANGLE|SWEEP_ANGLE) " | ForEach-Object { $_.Line -replace '\s*#.*', '' }

Write-Host ""
Write-Host "=== Results log ===" -ForegroundColor Cyan
if (Test-Path "$ScriptDir\results_docker.tsv") {
    Get-Content "$ScriptDir\results_docker.tsv"
} else {
    Write-Host "(no results.tsv yet)"
}

if ($NoRecord) {
    Write-Host "`nSkipping recording (-NoRecord)"
    exit 0
}

Write-Host ""
Write-Host "=== Recording MP4 ===" -ForegroundColor Cyan

# Swap in docker design, record, restore
$backupName = "design_backup_$PID.py"
Copy-Item "$ScriptDir\design.py" "$ScriptDir\$backupName"
Copy-Item "$ScriptDir\design_docker.py" "$ScriptDir\design.py"

try {
    Push-Location $ScriptDir
    & uv run visualize.py record -o $Output --lift --wake --dark --no-validate
    Pop-Location
} finally {
    # Always restore original
    Move-Item "$ScriptDir\$backupName" "$ScriptDir\design.py" -Force
}

Write-Host ""
Write-Host "Done: $Output" -ForegroundColor Green
