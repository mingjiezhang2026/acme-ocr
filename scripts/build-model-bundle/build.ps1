param(
  [string]$Version = "0.1.0",
  [string]$ModelKey = "ppocr-zh"
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
py -3 "$ScriptDir/build_model_bundle.py" --version $Version --model-key $ModelKey

