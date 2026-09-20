$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectPath = Join-Path $projectRoot "lg_capture_proxy\LgCaptureProxy.csproj"
$runtimeDir = Join-Path $projectRoot "lg_capture_proxy\bin\Release\net8.0\runtime_data"
$certPath = Join-Path $runtimeDir "certs\newbest_capture_proxy.cer"

dotnet build $projectPath -c Release | Out-Null
dotnet run --project $projectPath -c Release -- --prepare-only | Out-Null

if (-not (Test-Path $certPath)) {
    throw "인증서 파일을 찾을 수 없습니다: $certPath"
}

certutil -user -addstore Root $certPath
Write-Host "설치 완료: $certPath"
