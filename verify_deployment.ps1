$ErrorActionPreference = "Stop"

$ExpectedEngine = "v7.7.1-tcea-commercial-evidence-stable"
$ExpectedApi = "7.7.1"

# Backend-only production files. Frontend is deployed separately through Cloudflare.
$required = @(
    "architecture_model.py",
    "commercial_contracts.py",
    "scan_execution_protocol.py",
    "pathway_markers.py",
    "hybrid_scanner.py",
    "scorer.py",
    "architect_review.py",
    "report_engine.py",
    "main.py",
    "learning_intelligence.py",
    "remediation_intelligence.py"
)

$missing = @()
foreach ($f in $required) {
    if (-not (Test-Path ".\\$f")) { $missing += $f }
}
if ($missing.Count -gt 0) {
    Write-Host "DEPLOYMENT BLOCKED - missing required backend files:" -ForegroundColor Red
    $missing | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    exit 1
}

$scanner = Get-Content .\hybrid_scanner.py -Raw
$main = Get-Content .\main.py -Raw
$report = Get-Content .\report_engine.py -Raw

# The canonical production engine version must live in HybridScanner.
if ($scanner -notmatch ('ENGINE_VERSION\s*=\s*"' + [regex]::Escape($ExpectedEngine) + '"')) {
    throw "HybridScanner ENGINE_VERSION is not $ExpectedEngine"
}

# main.py must derive API/system identity from HybridScanner rather than carry a stale hard-coded release.
if ($main -notmatch 'SCANNER_ENGINE_VERSION\s*=\s*getattr\(HybridScanner,\s*"ENGINE_VERSION"') {
    throw "main.py is not deriving SCANNER_ENGINE_VERSION from HybridScanner."
}
if ($main -notmatch 'version\s*=\s*API_VERSION') {
    throw "main.py FastAPI version is not derived from API_VERSION."
}
if ($main -match '7\.5\.0|7\.5\.3') {
    throw "main.py still contains a stale V7.5 scanner/API version literal."
}

# Report engine must render the scan's actual engine version, not a hard-coded historical label.
if ($report -notmatch 'scanner_engine_version') {
    throw "report_engine.py is not carrying scanner_engine_version."
}
if ($report -notmatch 'engine_label') {
    throw "report_engine.py is not deriving the displayed engine label dynamically."
}
if ($report -match 'TRILLOKA TELEMETRY & EXECUTIVE AUDIT\s*—\s*V7\.5\.3') {
    throw "report_engine.py still hard-codes the V7.5.3 report label."
}

# Import the actual runtime and verify the values Python exposes.
$runtime = python -c "import main; print(main.scanner.ENGINE_VERSION); print(main.app.version)"
if ($LASTEXITCODE -ne 0) { throw "Python runtime import of main.py failed." }
$lines = @($runtime | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne "" })
if ($lines.Count -lt 2) { throw "Could not read runtime engine/API versions." }
if ($lines[-2] -ne $ExpectedEngine) {
    throw "Runtime scanner version is '$($lines[-2])', expected '$ExpectedEngine'."
}
if ($lines[-1] -ne $ExpectedApi) {
    throw "Runtime API version is '$($lines[-1])', expected '$ExpectedApi'."
}

# Fail only on stale V7.5 *release literals* in core production files.
# Numeric weights such as 7.5 are intentionally ignored. Learning/remediation
# keep independent component version labels and are reported separately below.
$coreFiles = @(
    "main.py",
    "hybrid_scanner.py",
    "report_engine.py",
    "scorer.py",
    "architect_review.py",
    "commercial_contracts.py",
    "scan_execution_protocol.py",
    "pathway_markers.py"
)
$stale = @()
foreach ($f in $coreFiles) {
    $text = Get-Content $f -Raw
    if ($text -match '(?i)(?:v7\.5\.[0-9]+|V7\.5\.[0-9]+)') {
        # Historical comments are not deployment identity. Show them for review,
        # but only block obvious executable/version-string assignments or report labels.
        $matches = Select-String -Path $f -Pattern '(?i)v7\.5\.[0-9]+|V7\.5\.[0-9]+'
        foreach ($m in $matches) {
            if ($m.Line -match 'ENGINE_VERSION|version\s*=|scanner_engine_version|TELEMETRY & EXECUTIVE AUDIT|system') {
                $stale += ('{0}:{1}: {2}' -f $f, $m.LineNumber, $m.Line.Trim())
            }
        }
    }
}
if ($stale.Count -gt 0) {
    Write-Host "DEPLOYMENT BLOCKED - stale core scanner release labels found:" -ForegroundColor Red
    $stale | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    exit 1
}

# Independent subsystem versions are allowed to differ from the scanner release.
$learningVersion = python -c "import learning_intelligence as x; print(getattr(x, '_VERSION', 'unknown'))"
$remediationVersion = python -c "from remediation_intelligence import build_outcome_remediation; r=build_outcome_remediation('primary_conversion_path','restaurant','reservation_event',[]); print((r or {}).get('remediation_engine','unknown'))"

Write-Host "V7.7.1 TCEA backend deployment preflight PASSED." -ForegroundColor Green
Write-Host "  Scanner engine : $ExpectedEngine" -ForegroundColor Green
Write-Host "  API version    : $ExpectedApi" -ForegroundColor Green
Write-Host "  Learning module: $($learningVersion | Select-Object -Last 1) (independently versioned)" -ForegroundColor DarkGray
Write-Host "  Remediation    : $($remediationVersion | Select-Object -Last 1) (independently versioned)" -ForegroundColor DarkGray
