$ErrorActionPreference = "Stop"
$required = @("architecture_model.py","hybrid_scanner.py","pathway_markers.py","main.py","report_engine.py","index.html","satirwaytojoy.jpg")
$missing = @()
foreach ($f in $required) { if (-not (Test-Path ".\\$f")) { $missing += $f } }
if ($missing.Count -gt 0) { Write-Host "DEPLOYMENT BLOCKED - missing required files:" -ForegroundColor Red; $missing | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }; exit 1 }
$report = Get-Content .\\report_engine.py -Raw; $scanner = Get-Content .\\hybrid_scanner.py -Raw; $index = Get-Content .\\index.html -Raw
if ($report -notmatch "At a Glance") { throw "Report renderer missing At a Glance." }
if ($report -notmatch "V7\.5\.3") { throw "Report engine is not V7.5.3." }
if ($scanner -notmatch 'ENGINE_VERSION = "v7\.5\.3"') { throw "Scanner engine is not V7.5.3." }
if ($index -notmatch "satirwaytojoy\.jpg") { throw "Index is not wired to staircase background." }
Write-Host "V7.5.3 deployment preflight PASSED." -ForegroundColor Green


