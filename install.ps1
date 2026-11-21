# Copy the orchestrator setup into a project's .claude\ folder.
# Usage: .\install.ps1 [-Target <project dir>] [-Force]
# Existing files are kept unless -Force is given; then run /orchestrator-init in Claude Code there.
# Works in Windows PowerShell 5.1 and PowerShell 7.
param(
    [string]$Target = ".",
    [switch]$Force
)
$ErrorActionPreference = "Stop"

$src = Join-Path $PSScriptRoot "template\.claude"
$targetRoot = (Resolve-Path $Target).Path
$dest = Join-Path $targetRoot ".claude"

git -C $targetRoot rev-parse --is-inside-work-tree *> $null
if ($LASTEXITCODE -ne 0) {
    Write-Warning "$targetRoot is not a git repository; /execute-plan needs git worktrees."
}

$copied = 0; $kept = 0
Get-ChildItem -Path $src -Recurse -File | Where-Object { $_.Extension -ne ".pyc" } | ForEach-Object {
    $rel = $_.FullName.Substring($src.Length).TrimStart('\', '/')
    $out = Join-Path $dest $rel
    if ((Test-Path $out) -and -not $Force) {
        Write-Output "kept     .claude\$rel (exists; -Force overwrites)"
        $kept++
        return
    }
    New-Item -ItemType Directory -Force -Path (Split-Path $out) | Out-Null
    Copy-Item -LiteralPath $_.FullName -Destination $out -Force
    $copied++
}

Write-Output ""
Write-Output "Copied $copied files into $dest ($kept kept)."
Write-Output "Next: open Claude Code in $targetRoot and run  /orchestrator-init"
