<#
.SYNOPSIS
  Runs the Skills Orchestrator benchmark: 4 tasks x 3 arms x 2 repeats.

.DESCRIPTION
  Each run is a fresh copy of fixtures/app in a throwaway folder and a fresh
  Claude Code session (`claude -p`). The arms are:

    baseline      no skills, no plugin
    superpowers   the Superpowers plugin only
    orchestrator  this repository as a plugin, with Superpowers also loaded

  `--plugin-dir` is repeatable, so the orchestrator arm gets both plugins and
  the comparison stays about orchestration rather than which skill set is
  installed.

  Nothing is written into the repository. Work folders, logs and the graded
  report land in -RunsRoot (default: %TEMP%\skills-orchestrator-benchmark).

.EXAMPLE
  .\run-benchmark.ps1 -List
  .\run-benchmark.ps1 -Arm orchestrator -Task 1 -Repeat 1 -DryRun
  .\run-benchmark.ps1 -SuperpowersDir C:\path\to\superpowers
#>
[CmdletBinding()]
param(
    [ValidateSet('all', 'baseline', 'superpowers', 'orchestrator')]
    [string]$Arm = 'all',
    [string]$Task = 'all',
    [string]$Repeat = 'all',
    [string]$RunsRoot,
    [string]$SuperpowersDir,
    [string]$ClaudeBin = 'claude',
    [switch]$DryRun,
    [switch]$List,
    [switch]$GradeOnly
)

$ErrorActionPreference = 'Continue'

$BenchDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Repo = Split-Path -Parent (Split-Path -Parent $BenchDir)
$Fixture = Join-Path $BenchDir 'fixtures\app'
$Grader = Join-Path $BenchDir 'grade.py'

if (-not $RunsRoot) {
    $RunsRoot = Join-Path ([IO.Path]::GetTempPath()) 'skills-orchestrator-benchmark'
}
$WorkRoot = Join-Path $RunsRoot 'work'
$OutRoot = Join-Path $RunsRoot 'out'

$Arms = [ordered]@{
    'baseline'     = @{ Plugin = $null; Superpowers = $false }
    'superpowers'  = @{ Plugin = $null; Superpowers = $true }
    'orchestrator' = @{ Plugin = $Repo; Superpowers = $true }
}

$Tasks = [ordered]@{
    '1' = 'Fix the login bug in src/auth.py and write REPORT.md for a manager with the headings Summary, Root cause, Fix and Verification.'
    '2' = 'Add a failing test that reproduces the invoice rounding bug, then fix src/invoice_parser.py so the invoice tests pass.'
    '3' = 'Update docs/API.md so it matches src/api.py: the routes, status codes and duplicate-order behaviour.'
    '4' = 'Analyse data/sales.csv with a short Python script and write summary.md with the total revenue, the top region and any data quality problem.'
}

function Selected($value, $all) {
    if ($value -eq 'all') { return $all }
    return @($value)
}

function Or-Default {
    param($Value, $Fallback)
    if ($null -eq $Value -or $Value -eq '') { $Fallback } else { $Value }
}

$armNames = Selected $Arm @('baseline', 'superpowers', 'orchestrator')
$taskIds = Selected $Task @('1', '2', '3', '4')
$repeats = Selected $Repeat @(1, 2)

if ($List) {
    foreach ($a in $armNames) {
        foreach ($t in $taskIds) {
            foreach ($r in $repeats) {
                '{0,-12} task={1} repeat={2} plugin={3} superpowers={4}' -f `
                    $a, $t, $r, (Or-Default $Arms[$a].Plugin '(none)'), $Arms[$a].Superpowers
            }
        }
    }
    return
}

if (-not $DryRun -and -not $GradeOnly) {
    if (-not (Test-Path $Grader)) { throw "missing grader: $Grader" }
    if (-not (Test-Path $Fixture)) { throw "missing fixture: $Fixture" }
    if (-not $SuperpowersDir -and ($armNames -contains 'superpowers' -or $armNames -contains 'orchestrator')) {
        throw "Pass -SuperpowersDir for the superpowers and orchestrator arms (or run -Arm baseline)."
    }
    if ($SuperpowersDir -and -not (Test-Path $SuperpowersDir)) {
        throw "Superpowers folder not found: $SuperpowersDir"
    }
}

if ($GradeOnly) {
    python $Grader $RunsRoot
    return
}

$claudeVersion = (& $ClaudeBin --version 2>&1) -join ' '

foreach ($a in $armNames) {
    $spec = $Arms[$a]
    foreach ($t in $taskIds) {
        foreach ($r in $repeats) {
            $name = "$a-t$t-r$r"
            $work = Join-Path $WorkRoot $name
            $log = Join-Path $OutRoot "$name.log"
            $debug = Join-Path $OutRoot "$name.debug.log"
            $meta = Join-Path $OutRoot "$name.meta.json"
            $prompt = $Tasks[$t]

            if ($DryRun) {
                "run        : $name"
                "work dir   : $work"
                "plugin     : $(Or-Default $spec.Plugin '(none)')"
                "superpowers: $($spec.Superpowers)"
                "message    : $prompt"
                "log        : $log"
                ""
                continue
            }

            Remove-Item $work -Recurse -Force -ErrorAction SilentlyContinue
            New-Item $work -ItemType Directory -Force | Out-Null
            Copy-Item -Path (Join-Path $Fixture '*') -Destination $work -Recurse -Force
            git -C $work init -q 2>$null
            git -C $work -c user.email=bench@example.com -c user.name=bench add -A
            git -C $work -c user.email=bench@example.com -c user.name=bench commit -qm "fixture"

            New-Item $OutRoot -ItemType Directory -Force | Out-Null

            $cliArgs = @(
                '-p', $prompt,
                '--output-format', 'stream-json',
                '--verbose',
                '--debug=hooks',
                '--debug-file', $debug,
                '--permission-mode', 'acceptEdits',
                '--allowedTools', 'Read,Grep,Glob,Bash,Write,Edit'
            )
            if ($spec.Plugin) { $cliArgs += @('--plugin-dir', $spec.Plugin) }
            if ($spec.Superpowers) { $cliArgs += @('--plugin-dir', $SuperpowersDir) }

            Write-Host "running $name ..."
            Push-Location $work
            try {
                $sw = [Diagnostics.Stopwatch]::StartNew()
                $output = & $ClaudeBin @cliArgs 2>&1
                $code = $LASTEXITCODE
                $sw.Stop()
            }
            finally {
                Pop-Location
            }
            $output | Out-File -FilePath $log -Encoding utf8

            [ordered]@{
                run = $name
                arm = $a
                task = [int]$t
                repeat = [int]$r
                exit = $code
                seconds = [math]::Round($sw.Elapsed.TotalSeconds, 1)
                claude = $claudeVersion
                commit = (& git -C $Repo rev-parse --short HEAD)
                superpowers = (Or-Default $SuperpowersDir '')
            } | ConvertTo-Json | Out-File -FilePath $meta -Encoding utf8
        }
    }
}

if (-not $DryRun) {
    python $Grader $RunsRoot
}
