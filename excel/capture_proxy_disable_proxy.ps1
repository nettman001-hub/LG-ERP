$ErrorActionPreference = "Stop"

$regPath = "HKCU:\Software\Microsoft\Windows\CurrentVersion\Internet Settings"
Set-ItemProperty -Path $regPath -Name ProxyEnable -Value 0

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

Write-Host "Windows proxy disabled"
