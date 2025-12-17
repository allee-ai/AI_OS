#!/usr/bin/env pwsh
Set-StrictMode -Version Latest
Push-Location -LiteralPath $PSScriptRoot

if (Test-Path -LiteralPath .\start.ps1) {
    & .\start.ps1
} elseif (Test-Path -LiteralPath .\start.bat) {
    Start-Process cmd -ArgumentList '/c','start.bat' -Wait
} elseif (Test-Path -LiteralPath .\start.sh) {
    if (Get-Command wsl -ErrorAction SilentlyContinue) {
        wsl bash ./start.sh
    } elseif (Get-Command bash -ErrorAction SilentlyContinue) {
        bash ./start.sh
    } else {
        Write-Host "No shell found to run start.sh. Run it manually."
    }
}

Pop-Location
Read-Host -Prompt "Press Enter to close"
