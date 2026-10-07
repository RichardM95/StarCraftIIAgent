# Extract latest SC2 playtest Alerts/ScriptError logs into bugreport.txt.
$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Get-Command python -ErrorAction SilentlyContinue
if (-not $Python) {
    $Python = Get-Command py -ErrorAction SilentlyContinue
    if ($Python) {
        & py -3 "$PSScriptRoot\extract-playtest-bugreport.py" @args
        exit $LASTEXITCODE
    }
    throw "Python not found on PATH."
}
& $Python.Source "$PSScriptRoot\extract-playtest-bugreport.py" @args
exit $LASTEXITCODE
