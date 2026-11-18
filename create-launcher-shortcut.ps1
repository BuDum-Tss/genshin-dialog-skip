<#
.SYNOPSIS
  Создаёт на рабочем столе ярлык, который запускает Genshin Skip и затем лаунчер игры.

.EXAMPLE
  .\create-launcher-shortcut.ps1 -LauncherPath "C:\Program Files\HoYoPlay\launcher.exe" -LauncherArgs "--game=hk4e_global"

.EXAMPLE
  .\create-launcher-shortcut.ps1 "D:\Games\Genshin Impact\launcher.exe" -SkipPath "D:\Tools\GenshinSkip.exe"

  Скрипт кладут рядом с GenshinSkip.exe — тогда -SkipPath указывать не нужно.
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$LauncherPath,                     # путь к лаунчеру (exe)

    [string]$LauncherArgs = "",                # аргументы лаунчера, например --game=hk4e_global
    [string]$SkipPath = "",                    # по умолчанию: GenshinSkip.exe рядом со скриптом
    [string]$Name = "Genshin + Skip",          # имя ярлыка
    [string]$OutputDir = [Environment]::GetFolderPath("Desktop")
)

$ErrorActionPreference = "Stop"

if (-not $SkipPath) { $SkipPath = Join-Path $PSScriptRoot "GenshinSkip.exe" }
if (-not (Test-Path -LiteralPath $LauncherPath -PathType Leaf)) { throw "Лаунчер не найден: $LauncherPath" }
if (-not (Test-Path -LiteralPath $SkipPath -PathType Leaf)) { throw "GenshinSkip.exe не найден: $SkipPath (положите скрипт рядом с GenshinSkip.exe или укажите -SkipPath)" }
$LauncherPath = (Resolve-Path -LiteralPath $LauncherPath).Path
$SkipPath = (Resolve-Path -LiteralPath $SkipPath).Path

function Q([string]$s) { "'" + $s.Replace("'", "''") + "'" }   # экранирование для одинарных кавычек PowerShell

$cmd = "if (-not (Get-Process GenshinSkip -ErrorAction SilentlyContinue)) { Start-Process -FilePath $(Q $SkipPath) }; "
if ($LauncherArgs) { $cmd += "Start-Process -FilePath $(Q $LauncherPath) -ArgumentList $(Q $LauncherArgs)" }
else { $cmd += "Start-Process -FilePath $(Q $LauncherPath)" }

$lnkPath = Join-Path $OutputDir "$Name.lnk"
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($lnkPath)
$s.TargetPath = "powershell.exe"
$s.Arguments = "-NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command `"$($cmd.Replace('"','\"'))`""
$s.WorkingDirectory = Split-Path $LauncherPath
$s.IconLocation = "$LauncherPath,0"
$s.Description = "Запустить Genshin Skip и игру"
$s.Save()

Write-Host "Ярлык создан: $lnkPath"
