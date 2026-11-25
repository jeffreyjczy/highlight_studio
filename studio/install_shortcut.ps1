# Creates "Highlight Studio" shortcuts on the Desktop and in the Start menu.
$ErrorActionPreference = 'Stop'
$studio  = Split-Path -Parent $MyInvocation.MyCommand.Path
$pipe    = Split-Path -Parent $studio
$pythonw = Join-Path $pipe '.venv\Scripts\pythonw.exe'
$main    = Join-Path $studio 'main.py'
$icon    = Join-Path $studio 'studio.ico'
if (-not (Test-Path $pythonw)) { throw "Missing $pythonw" }

$desktop = [Environment]::GetFolderPath('Desktop')
$start   = Join-Path ([Environment]::GetFolderPath('Programs')) 'Highlight Studio.lnk'
$shell = New-Object -ComObject WScript.Shell
foreach ($path in @((Join-Path $desktop 'Highlight Studio.lnk'), $start)) {
    $lnk = $shell.CreateShortcut($path)
    $lnk.TargetPath       = $pythonw
    $lnk.Arguments        = "`"$main`""
    $lnk.WorkingDirectory = $studio
    $lnk.IconLocation     = "$icon,0"
    $lnk.Description      = 'Make, browse and merge gameplay highlights'
    $lnk.Save()
    Write-Output "Created $path"
}
