<#
.SYNOPSIS
Run Unity import/collector integration in a disposable project without using desktop UI.
.EXAMPLE
pwsh -File .\tools\run_unity_integration.ps1 -FixtureDir F:\CodexTemp\ExportLens\fixtures
#>
[CmdletBinding()]
param(
    [string]$UnityEditor = 'F:\Unity Engine\Editors\2022.3.22f1\Editor\Unity.exe',
    [Parameter(Mandatory = $true)][string]$FixtureDir,
    [string]$ProjectDir = 'F:\CodexTemp\ExportLens\Unity2022',
    [string]$OutputDir = 'F:\CodexTemp\ExportLens\unity-results',
    [string]$BaselineFbx = 'ordered_slots.fbx',
    [string]$EditorVersion = '2022.3.22f1',
    [int]$TimeoutSeconds = 900,
    [switch]$NoWait,
    [switch]$CaptureOnly
)
$ErrorActionPreference = 'Stop'
$repository = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$temporaryRoot = [IO.Path]::GetFullPath('F:\CodexTemp\ExportLens')
$projectPath = [IO.Path]::GetFullPath($ProjectDir)
$outputPath = [IO.Path]::GetFullPath($OutputDir)
if (-not $projectPath.StartsWith($temporaryRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw "Disposable Unity project must stay below $temporaryRoot."
}
if (-not (Test-Path -LiteralPath $UnityEditor -PathType Leaf)) { throw "Unity Editor not found: $UnityEditor" }
if (-not (Test-Path -LiteralPath $FixtureDir -PathType Container)) { throw "Fixture folder not found: $FixtureDir" }
if (-not $CaptureOnly -and -not (Test-Path -LiteralPath (Join-Path $FixtureDir $BaselineFbx) -PathType Leaf)) { throw "Baseline FBX not found: $BaselineFbx" }
if (Get-CimInstance Win32_Process -Filter "Name = 'Unity.exe'" | Where-Object { $_.ExecutablePath -match '\\Editor\\Unity\.exe$' }) {
    throw 'Another Unity Editor is running. Coordinate resource use before starting this isolated batch.'
}
$null = New-Item -ItemType Directory -Path $projectPath, $outputPath, (Join-Path $projectPath 'Assets'), (Join-Path $projectPath 'Packages'), (Join-Path $projectPath 'ProjectSettings'), (Join-Path $temporaryRoot 'process-temp') -Force
$manifest = @{ dependencies = @{ 'com.exportlens.editor' = ('file:' + (Join-Path $repository 'unity').Replace('\', '/')) } } | ConvertTo-Json -Depth 4
[IO.File]::WriteAllText((Join-Path $projectPath 'Packages\manifest.json'), $manifest, [Text.UTF8Encoding]::new($false))
[IO.File]::WriteAllText((Join-Path $projectPath 'ProjectSettings\ProjectVersion.txt'), "m_EditorVersion: $EditorVersion`n", [Text.UTF8Encoding]::new($false))
$logPath = Join-Path $outputPath 'unity-editor.log'
$resultPath = Join-Path $outputPath 'unity-batch-result.json'
# Remove only this prior status file, so a compiler failure cannot leave stale success evidence.
if (Test-Path -LiteralPath $resultPath -PathType Leaf) { Remove-Item -LiteralPath $resultPath -Force }
function Quote-UnityArgument([string]$Value) {
    if ($Value.Contains('"')) { throw 'Double quotes are not supported in Unity argument paths.' }
    return '"' + $Value + '"'
}
$unityArguments = @(
    '-batchmode', '-nographics', '-job-worker-count', '1', '-projectPath', (Quote-UnityArgument $projectPath),
    '-logFile', (Quote-UnityArgument $logPath), '-executeMethod', 'ExportLens.Editor.BatchIntegration.Run',
    '-exportLensFixtures', (Quote-UnityArgument ([IO.Path]::GetFullPath($FixtureDir))),
    '-exportLensOutput', (Quote-UnityArgument $outputPath), '-exportLensBaseline', (Quote-UnityArgument $BaselineFbx)
)
if ($CaptureOnly) { $unityArguments += @('-exportLensCaptureOnly', 'true') }
$priorTemp = $env:TEMP
$priorTmp = $env:TMP
try {
    $env:TEMP = Join-Path $temporaryRoot 'process-temp'
    $env:TMP = $env:TEMP
    $process = Start-Process -FilePath $UnityEditor -ArgumentList $unityArguments -WorkingDirectory $projectPath -PassThru -WindowStyle Hidden
    $process.PriorityClass = [Diagnostics.ProcessPriorityClass]::BelowNormal
    # Keep import/compilation responsive to the foreground game and limit worker pressure.
    if ([Environment]::ProcessorCount -gt 2) { $process.ProcessorAffinity = [IntPtr]3 }
}
finally {
    $env:TEMP = $priorTemp
    $env:TMP = $priorTmp
}
Write-Output ([ordered]@{ pid = $process.Id; project = $projectPath; log = $logPath; result = $resultPath } | ConvertTo-Json -Compress)
if ($NoWait) { return }
$startedAt = Get-Date
$lastUpdate = $startedAt
while (-not $process.WaitForExit(1000)) {
    $now = Get-Date
    if (($now - $lastUpdate).TotalSeconds -ge 30) {
        Write-Output "Waiting for isolated Unity batch PID $($process.Id); elapsed $([int]($now - $startedAt).TotalSeconds)s. Log: $logPath"
        $lastUpdate = $now
    }
    if (($now - $startedAt).TotalSeconds -gt $TimeoutSeconds) {
        $process.Kill()
        throw "Unity batch exceeded $TimeoutSeconds seconds. Its isolated process was stopped. Inspect $logPath"
    }
}
if ($process.ExitCode -ne 0) { throw "Unity exited with code $($process.ExitCode). Inspect $logPath" }
if (-not (Test-Path -LiteralPath $resultPath -PathType Leaf)) { throw "Unity did not write batch evidence. Inspect $logPath" }
$result = Get-Content -LiteralPath $resultPath -Raw | ConvertFrom-Json
if (-not $result.success) { throw "Unity collection failed: $($result.error)" }
Write-Output "Unity $($result.unity_version): captured $($result.captures.Count) FBX snapshots. Evidence: $resultPath"
