param(
  [string]$Version = "0.1.0",
  [string]$Platform = "",
  [string]$Wheelhouse = ""
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ArgsList = @("$ScriptDir/build_runtime_bundle.py", "--version", $Version)

if ($Platform -ne "") {
  $ArgsList += @("--platform", $Platform)
}

if ($Wheelhouse -ne "") {
  $ArgsList += @("--wheelhouse", $Wheelhouse)
}

py -3 @ArgsList

