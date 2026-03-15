# Pull all experiment data from running Docker container and export to
# auto-research-results/vN-<tag>/
#
# Usage:
#   .\export_docker.ps1 mar15       # exports to auto-research-results/v3-mar15/
#   .\export_docker.ps1 mar15 -Stop # exports then stops the container

param(
    [Parameter(Mandatory=$true)]
    [string]$Tag,
    [switch]$Stop
)

$ErrorActionPreference = "Stop"
$Container = "auto-ornithopter"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ResultsBase = Join-Path $ScriptDir "auto-research-results"

# Find docker
$Docker = "docker"
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    $DockerPath = "C:\Program Files\Docker\Docker\resources\bin\docker.exe"
    if (Test-Path $DockerPath) { $Docker = $DockerPath }
    else { Write-Error "docker not found"; exit 1 }
}

# Check container exists
$running = & $Docker ps -a --format '{{.Names}}' 2>&1
if ($running -notcontains $Container) {
    Write-Error "Container '$Container' not found"
    exit 1
}

# Determine next version number
if (-not (Test-Path $ResultsBase)) { New-Item -ItemType Directory -Path $ResultsBase | Out-Null }
$existing = Get-ChildItem $ResultsBase -Directory -Filter "v*-$Tag" | Sort-Object Name
if ($existing) {
    $lastVersion = [int]($existing[-1].Name -replace "v(\d+)-.*", '$1')
    $nextVersion = $lastVersion + 1
} else {
    $nextVersion = 1
}

$ExportDir = Join-Path $ResultsBase "v${nextVersion}-${Tag}"
$DesignsDir = Join-Path $ExportDir "designs"
New-Item -ItemType Directory -Path $DesignsDir -Force | Out-Null

Write-Host "=== Exporting to $ExportDir ===" -ForegroundColor Cyan

# Pull core files from container
Write-Host "Pulling files from container..."
& $Docker cp "${Container}:/app/results.tsv" "$ExportDir/results.tsv" 2>$null
& $Docker cp "${Container}:/app/design.py" "$ExportDir/design.py" 2>$null
& $Docker cp "${Container}:/app/sim_output.json" "$ExportDir/sim_output.json" 2>$null
& $Docker cp "${Container}:/app/run.log" "$ExportDir/run.log" 2>$null

# Extract every design.py version from git history inside the container
Write-Host "Extracting design history from git..."
$gitLog = & $Docker exec $Container git log --oneline --all -- design.py 2>$null
if ($gitLog) {
    foreach ($line in $gitLog) {
        $parts = $line -split ' ', 2
        $hash = $parts[0]
        $msg = if ($parts.Length -gt 1) { $parts[1] } else { "no_message" }
        $safeMsg = ($msg -replace '[/:\\<>|"?*]', '_').Substring(0, [Math]::Min($msg.Length, 50))
        $filename = "${hash}_${safeMsg}.py"
        & $Docker exec $Container git show "${hash}:design.py" 2>$null | Out-File -FilePath (Join-Path $DesignsDir $filename) -Encoding utf8
    }
    $designCount = (Get-ChildItem $DesignsDir -Filter "*.py").Count
    Write-Host "  Exported $designCount design snapshots"
}

# Show summary
Write-Host ""
Write-Host "=== Results ===" -ForegroundColor Cyan
if (Test-Path "$ExportDir/results.tsv") {
    Get-Content "$ExportDir/results.tsv"
} else {
    Write-Host "(no results.tsv)"
}

# Record MP4 of the best design
Write-Host ""
Write-Host "=== Recording best design MP4 ===" -ForegroundColor Cyan
$mp4Path = Join-Path $ExportDir "best_design.mp4"
$backupDesign = Join-Path $ScriptDir "design_backup_export_$PID.py"
Copy-Item (Join-Path $ScriptDir "design.py") $backupDesign
Copy-Item (Join-Path $ExportDir "design.py") (Join-Path $ScriptDir "design.py")
try {
    Push-Location $ScriptDir
    & uv run visualize.py record -o $mp4Path --lift --wake --dark --no-validate
    Pop-Location
    Write-Host "  Saved: $mp4Path" -ForegroundColor Green
} catch {
    Write-Host "  Recording failed: $_" -ForegroundColor Red
    Pop-Location
} finally {
    Move-Item $backupDesign (Join-Path $ScriptDir "design.py") -Force
}

Write-Host ""
Write-Host "Exported to: $ExportDir" -ForegroundColor Green

if ($Stop) {
    Write-Host ""
    Write-Host "=== Stopping container ===" -ForegroundColor Yellow
    & $Docker stop $Container | Out-Null
    & $Docker rm $Container 2>$null | Out-Null
    Write-Host "Container stopped."
}
