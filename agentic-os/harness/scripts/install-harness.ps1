# Install portfolio harness from Windows
param(
    [string]$Project = "",
    [switch]$All,
    [switch]$Merge,
    [switch]$DryRun
)

$Repo = Split-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) -Parent

$args = @()
if ($All) { $args += "--all" }
elseif ($Project) { $args += "--project", $Project }
if ($Merge) { $args += "--merge" }
if ($DryRun) { $args += "--dry-run" }

Push-Location $Repo
try {
    python (Join-Path $Repo "agentic-os\harness\install.py") @args
} finally {
    Pop-Location
}
