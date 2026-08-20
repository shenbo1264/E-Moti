param(
    [Parameter(Mandatory = $true)]
    [string]$TargetRepo,
    [string]$PythonPath = "python",
    [switch]$SkipFullTests,
    [switch]$RunWindowsBuild,
    [switch]$RunInstallerBuild,
    [string]$SubmissionZip = "",
    [switch]$RunPrivateApiSmoke,
    [switch]$RequireOnlineProviders,
    [switch]$Force
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$Runner = Join-Path $ScriptRoot "apply_and_verify_emoti_overlay.py"
$Report = Join-Path $TargetRepo "artifacts\plugin-overlay-verification\apply_and_verify_report.json"

$Args = @(
    $Runner,
    $TargetRepo,
    "--python", $PythonPath,
    "--report", $Report
)
if ($SkipFullTests) { $Args += "--skip-full-tests" }
if ($RunWindowsBuild) { $Args += "--run-windows-build" }
if ($RunInstallerBuild) { $Args += "--run-installer-build" }
if ($SubmissionZip) { $Args += @("--submission-zip", $SubmissionZip) }
if ($RunPrivateApiSmoke) { $Args += "--run-private-api-smoke" }
if ($RequireOnlineProviders) { $Args += "--require-online-providers" }
if ($Force) { $Args += "--force" }

& $PythonPath @Args
if ($LASTEXITCODE -ne 0) {
    throw "E-Moti overlay verification failed with exit code $LASTEXITCODE. See $Report"
}
Write-Host "E-Moti overlay verification passed. Report: $Report"
