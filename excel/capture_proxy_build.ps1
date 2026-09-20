$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectPath = Join-Path $projectRoot "lg_capture_proxy\LgCaptureProxy.csproj"

dotnet build $projectPath -c Release
