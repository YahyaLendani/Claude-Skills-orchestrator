<#
.SYNOPSIS
  Runs one arm of the Round C behavior scenarios in a throwaway project.

.DESCRIPTION
  Each arm is a fresh Claude Code session (`claude -p`) with a clean project
  folder and one of four installs: the v1.2.0 skill copied in (baseline), the
  v1.3.0 skill copied in (copy install), this repository as a plugin, or the
  plugin with the SessionStart hook removed.

  Scenario arms c33-c39 send that scenario's Prompt as the whole user message,
  so a leading `/orchestrate` is parsed as a slash command instead of being
  buried in a batch. The baseline arms send Setup + Prompt, because the
  components being tested do not exist in that install.

  Nothing is written into the repository. Results land in the runs folder
  (default: %TEMP%\skills-orchestrator-behavior) as, per arm:
    out\<arm>.log        merged stdout/stderr of the session
    out\<arm>.debug.log  debug log filtered to hooks
    out\<arm>.files.txt  project changes, plugin-folder dirt, user state
    out\<arm>.meta.txt   versions, commit, skill fingerprint, exit code

.EXAMPLE
  .\run-behavior.ps1 -List
  .\run-behavior.ps1 -Arm c36 -DryRun
  .\run-behavior.ps1 -Arm c36
#>
[CmdletBinding()]
param(
    [string]$Arm,
    [switch]$List,
    [switch]$DryRun,
    [string]$RunsRoot,
    [string]$ClaudeBin = 'claude'
)

$ErrorActionPreference = 'Continue'

$ToolsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$Repo     = Split-Path -Parent (Split-Path -Parent $ToolsDir)
$Fixtures = Join-Path $ToolsDir 'fixtures'
$Seed     = Join-Path $ToolsDir 'seed'
$Prompts  = Join-Path $ToolsDir 'prompts'

if (-not $RunsRoot) {
    $RunsRoot = Join-Path ([IO.Path]::GetTempPath()) 'skills-orchestrator-behavior'
}

$WorkRoot  = Join-Path $RunsRoot 'work'
$OutRoot   = Join-Path $RunsRoot 'out'
$HookOff   = Join-Path $RunsRoot 'plugin-nohook'
$UserState = Join-Path $HOME '.claude\skills-orchestrator'

function Or-Default {
    param($Value, $Fallback)
    if ($null -eq $Value -or $Value -eq '') { $Fallback } else { $Value }
}

$Arms = [ordered]@{
    'baseline-a' = @{ Prompt='baseline-a.md'; Skill='v1.2.0'; Plugin=$null;    SeedState=$false; Scenario='33-36'; Batched=$true }
    'baseline-b' = @{ Prompt='baseline-b.md'; Skill='v1.2.0'; Plugin=$null;    SeedState=$false; Scenario='37-40'; Batched=$true }
    'c33'        = @{ Prompt='c33.md';        Skill=$null;    Plugin=$Repo;    SeedState=$false; Scenario='33' }
    'c34'        = @{ Prompt='c34.md';        Skill=$null;    Plugin=$Repo;    SeedState=$false; Scenario='34' }
    'c35'        = @{ Prompt='c35.md';        Skill=$null;    Plugin=$Repo;    SeedState=$false; Scenario='35' }
    'c36'        = @{ Prompt='c36.md';        Skill=$null;    Plugin=$Repo;    SeedState=$false; Scenario='36' }
    'c37'        = @{ Prompt='c37.md';        Skill='v1.3.0'; Plugin=$null;    SeedState=$false; Scenario='37' }
    'c38'        = @{ Prompt='c38.md';        Skill=$null;    Plugin=$HookOff; SeedState=$false; Scenario='38' }
    'c39'        = @{ Prompt='c39.md';        Skill=$null;    Plugin=$Repo;    SeedState=$true;  Scenario='39' }
}

if ($List -or -not $Arm) {
    $Arms.GetEnumerator() | ForEach-Object {
        '{0,-12} scenario={1,-6} prompt={2,-16} install={3,-5} plugin={4} seed={5}' -f `
            $_.Key, $_.Value.Scenario, $_.Value.Prompt,
            (Or-Default $_.Value.Skill 'plugin'),
            (Or-Default $_.Value.Plugin '-'),
            $_.Value.SeedState
    }
    return
}

if (-not $Arms.Contains($Arm)) { throw "Unknown arm '$Arm'. Use -List." }
$spec = $Arms[$Arm]

$Work       = Join-Path $WorkRoot $Arm
$Log        = Join-Path $OutRoot "$Arm.log"
$Debug      = Join-Path $OutRoot "$Arm.debug.log"
$Files      = Join-Path $OutRoot "$Arm.files.txt"
$Meta       = Join-Path $OutRoot "$Arm.meta.txt"
$PromptFile = Join-Path $Prompts $spec.Prompt

foreach ($p in @($Repo, $Fixtures, $PromptFile)) {
    if (-not (Test-Path $p)) { throw "missing $p" }
}

function Invoke-Git {
    param([string[]]$GitArgs, [string]$WorkingDirectory)
    $out = & git -C $WorkingDirectory @GitArgs 2>&1
    $code = $LASTEXITCODE
    if ($code -ne 0) { throw "git $($GitArgs -join ' ') failed: $out" }
    return ($out | Where-Object { $_ -isnot [System.Management.Automation.ErrorRecord] })
}

function Remove-Dir {
    param([string]$Path)
    if (Test-Path $Path) { cmd /c "rmdir /s /q `"$Path`"" | Out-Null }
    if (Test-Path $Path) { throw "could not remove $Path" }
}

# --- reset the project folder ------------------------------------------------
Remove-Dir $Work
New-Item $Work -ItemType Directory | Out-Null
Copy-Item (Join-Path $Fixtures '*') $Work -Recurse -Force

Invoke-Git @('init', '-q', '-b', 'main') $Work | Out-Null
Invoke-Git @('add', '-A') $Work | Out-Null
Invoke-Git @('-c','user.name=fixture','-c','user.email=fixture@example.com',
             'commit','-q','-m','fixture project') $Work | Out-Null

# --- install the skill, if this arm uses a copied one ------------------------
if ($spec.Skill) {
    $skillsDir = Join-Path $Work '.claude\skills'
    New-Item $skillsDir -ItemType Directory -Force | Out-Null
    $tarball = Join-Path ([IO.Path]::GetTempPath()) "so-skill-$Arm.tar"
    if (Test-Path $tarball) { Remove-Item $tarball -Force }
    & git -C $Repo archive --format=tar -o $tarball $spec.Skill skills-orchestrator
    if ($LASTEXITCODE -ne 0) { throw "git archive $($spec.Skill) failed" }
    & tar -x -f $tarball -C $skillsDir
    $tarCode = $LASTEXITCODE
    Remove-Item $tarball -Force
    if ($tarCode -ne 0) { throw "tar extract failed for $($spec.Skill)" }
    if (-not (Test-Path (Join-Path $skillsDir 'skills-orchestrator\SKILL.md'))) {
        throw "skill copy failed for $($spec.Skill)"
    }
}

# --- build the hook-removed plugin copy -------------------------------------
if ($spec.Plugin -eq $HookOff) {
    Remove-Dir $HookOff
    New-Item $HookOff -ItemType Directory | Out-Null
    $items = Get-ChildItem $Repo -Force | Where-Object { $_.Name -notin @('.git', 'tests') }
    foreach ($item in $items) { Copy-Item $item.FullName $HookOff -Recurse -Force }
    @{ description = 'Hooks for Skills Orchestrator'; hooks = @{} } |
        ConvertTo-Json -Depth 5 | Set-Content (Join-Path $HookOff 'hooks\hooks.json') -Encoding utf8
}

# --- seed memory, scores and cards for scenario 39 ---------------------------
if ($spec.SeedState) {
    foreach ($f in @('project\memory.md','project\scores.md','user\memory.md','user\scores.md','user\cards\pdf.md')) {
        if (-not (Test-Path (Join-Path $Seed $f))) { throw "missing seed file $f" }
    }
    if (-not $DryRun) {
        if (Test-Path $UserState) { throw "$UserState already exists; remove it before a seeded run" }
        New-Item (Join-Path $Work '.claude\skills-orchestrator') -ItemType Directory -Force | Out-Null
        Copy-Item (Join-Path $Seed 'project\*') (Join-Path $Work '.claude\skills-orchestrator') -Force

        New-Item (Join-Path $UserState 'cards') -ItemType Directory -Force | Out-Null
        Copy-Item (Join-Path $Seed 'user\memory.md') $UserState -Force
        Copy-Item (Join-Path $Seed 'user\scores.md') $UserState -Force
        Copy-Item (Join-Path $Seed 'user\cards\pdf.md') (Join-Path $UserState 'cards') -Force
    }
}

# --- assemble the command ----------------------------------------------------
$prompt = Get-Content $PromptFile -Raw -Encoding UTF8
$cliArgs = @(
    '-p', $prompt.TrimEnd(),
    '--output-format', 'stream-json',
    '--verbose',
    '--debug=hooks',
    '--debug-file', $Debug,
    '--permission-mode', 'acceptEdits',
    '--allowedTools', 'Read,Grep,Glob,Bash,Write,Edit'
)
if ($spec.Plugin) { $cliArgs += @('--plugin-dir', $spec.Plugin) }

$repoDirtyBefore = (& git -C $Repo status --porcelain) -join "`n"

if ($DryRun) {
    "arm        : $Arm (scenario $($spec.Scenario))"
    "work dir   : $Work"
    "prompt     : $PromptFile"
    "message    : $($prompt.Trim())"
    "plugin dir : $(Or-Default $spec.Plugin '(none)')"
    "skill      : $(Or-Default $spec.Skill '(none)')"
    "seed state : $($spec.SeedState)"
    "log        : $Log"
    return
}

New-Item $OutRoot -ItemType Directory -Force | Out-Null

# --- run ---------------------------------------------------------------------
Push-Location $Work
try {
    $sw = [Diagnostics.Stopwatch]::StartNew()
    $output = & $ClaudeBin @cliArgs 2>&1
    $code = $LASTEXITCODE
    $sw.Stop()
}
finally {
    Pop-Location
}
$output | Out-File -FilePath $Log -Encoding utf8

# --- what changed ------------------------------------------------------------
$lines = @()
$lines += '## project changes (git status)'
$lines += (& git -C $Work status --porcelain)
$lines += ''
$lines += '## project files (excluding .git)'
$lines += (Get-ChildItem $Work -Recurse -File -Force |
    Where-Object { $_.FullName -notmatch '\\\.git\\' } |
    ForEach-Object { $_.FullName.Substring($Work.Length + 1) })
$lines += ''
$lines += '## plugin folder dirt (git status of the repo)'
$dirtyAfter = ((& git -C $Repo status --porcelain) -join "`n")
if ($dirtyAfter -eq $repoDirtyBefore) { $lines += '(clean)' } else { $lines += $dirtyAfter }
$lines += ''
$lines += '## user state (~/.claude/skills-orchestrator)'
if (Test-Path $UserState) {
    $lines += (Get-ChildItem $UserState -Recurse -File | ForEach-Object { $_.FullName.Replace($HOME, '~') })
} else {
    $lines += '(absent)'
}
$lines | Out-File -FilePath $Files -Encoding utf8

# --- provenance --------------------------------------------------------------
$skillTag = Or-Default $spec.Skill '1.3.0 (plugin)'
$metaLines = @(
    "arm: $Arm",
    "scenario: $($spec.Scenario)",
    "run at: $(Get-Date -Format o)",
    "claude: $(& $ClaudeBin --version 2>&1)",
    "repo commit: $(git -C $Repo rev-parse HEAD)",
    "repo branch: $(git -C $Repo rev-parse --abbrev-ref HEAD)",
    "skill: $skillTag",
    "skill sha256: $((Get-FileHash (Join-Path $Repo 'skills-orchestrator\SKILL.md') -Algorithm SHA256).Hash.ToLower())",
    "plugin dir: $(Or-Default $spec.Plugin '(none)')",
    "seed state: $($spec.SeedState)",
    "prompt file: $($spec.Prompt)",
    "exit code: $code",
    "duration: $([int]$sw.Elapsed.TotalSeconds)s",
    "log: $Log"
)
$metaLines | Out-File -FilePath $Meta -Encoding utf8
$metaLines
