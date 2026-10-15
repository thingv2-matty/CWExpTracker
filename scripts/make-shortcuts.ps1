<#
    Create the double-click shortcuts.

    A .lnk stores an absolute path to a particular Python on a particular
    machine, so it is useless in a clone and is not committed. Run this once
    after cloning and the two shortcuts appear in the project root:

        powershell -ExecutionPolicy Bypass -File scripts\make-shortcuts.ps1

    Both point at pythonw.exe, which is the same interpreter without a console
    attached, so the window opens and nothing else does.
#>

$root = Split-Path -Parent $PSScriptRoot

$pythonw = "$env:LOCALAPPDATA\Programs\Python\Python312\pythonw.exe"
if (-not (Test-Path $pythonw)) {
    $found = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if ($found) { $pythonw = $found.Source }
}
if (-not (Test-Path $pythonw)) {
    Write-Error "Could not find pythonw.exe. Install Python, or edit this script."
    exit 1
}

$shell = New-Object -ComObject WScript.Shell

function New-Shortcut($name, $target, $description) {
    $path = Join-Path $root $name
    $link = $shell.CreateShortcut($path)
    $link.TargetPath = $pythonw
    $link.Arguments = '"' + (Join-Path $root $target) + '"'
    $link.WorkingDirectory = $root
    $link.Description = $description
    $link.Save()
    Write-Host "created $name"
}

New-Shortcut "Start EXP Tracker.lnk" "run.pyw" "MapleStory EXP tracker"
New-Shortcut "Caffeine.lnk" "tools\caffeine.py" `
    "Keep this machine awake without changing power settings"

Write-Host ""
Write-Host "Using $pythonw"
