param(
    [string]$ProxyServer = "127.0.0.1:8877"
)

$ErrorActionPreference = "Stop"

$regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
Set-ItemProperty -Path $regPath -Name ProxyServer -Value $ProxyServer
Set-ItemProperty -Path $regPath -Name ProxyEnable -Value 1
Set-ItemProperty -Path $regPath -Name ProxyOverride -Value "<local>"

Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class WinInetNative {
    [DllImport("wininet.dll", SetLastError=true)]
    public static extern bool InternetSetOption(IntPtr hInternet, int dwOption, IntPtr lpBuffer, int dwBufferLength);
}
"@

[WinInetNative]::InternetSetOption([IntPtr]::Zero, 39, [IntPtr]::Zero, 0) | Out-Null
[WinInetNative]::InternetSetOption([IntPtr]::Zero, 37, [IntPtr]::Zero, 0) | Out-Null

Write-Host "Windows proxy enabled: $ProxyServer"
