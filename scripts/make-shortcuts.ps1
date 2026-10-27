<#
    Create the double-click shortcuts.

    A .lnk stores an absolute path to a particular Python on a particular
    machine, so it is useless in a clone and is not committed. Setup.bat runs
    this, so nobody should ever have to type the line below:

        powershell -ExecutionPolicy Bypass -File scripts\make-shortcuts.ps1

    Start and Caffeine point at pythonw.exe, the same interpreter with no
    console attached, so the window opens and nothing else does. Teach and
    Debug point at python.exe instead, because both of them talk back and
    with pythonw there is nowhere for that to go.
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

$python = $pythonw -replace 'pythonw\.exe$', 'python.exe'
if (-not (Test-Path $python)) { $python = $pythonw }

$shell = New-Object -ComObject WScript.Shell

function New-Shortcut($name, $target, $description, $flags, $exe) {
    if (-not $exe) { $exe = $pythonw }
    $path = Join-Path $root $name
    $link = $shell.CreateShortcut($path)
    $link.TargetPath = $exe
    $arguments = '"' + (Join-Path $root $target) + '"'
    if ($flags) { $arguments = $arguments + ' ' + $flags }
    $link.Arguments = $arguments
    $link.WorkingDirectory = $root
    $link.Description = $description
    $link.Save()
    Write-Host "created $name"
}

New-Shortcut "Start EXP Tracker.lnk" "run.pyw" "MapleStory EXP tracker"

# These two keep their console on purpose: both of them talk back, and with
# pythonw there is nowhere for that to go. They exist so neither ever has to
# be typed.
New-Shortcut "Teach EXP Tracker.lnk" "run.py" `
    "Tell the tracker what the numbers say, for a new screen resolution" `
    "--teach" $python
New-Shortcut "Debug EXP Tracker.lnk" "run.py" `
    "Dump one capture, the glyph sizes and every score, then stop" `
    "--debug" $python

New-Shortcut "Caffeine.lnk" "tools\caffeine.py" `
    "Keep this machine awake without changing power settings"

Write-Host ""
Write-Host "Using $pythonw"
