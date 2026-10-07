param(
    [string]$Source = "",
    [string]$ModsDir = "",
    [switch]$Clean = $false
)

$ToolsDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PyScript = Join-Path $ToolsDir "deploy-mod.py"

$ArgsList = @($PyScript)
if ($Source) { $ArgsList += @("--source", $Source) }
if ($ModsDir) { $ArgsList += @("--mods-dir", $ModsDir) }
if ($Clean) { $ArgsList += @("--clean") }

python @ArgsList
exit $LASTEXITCODE
