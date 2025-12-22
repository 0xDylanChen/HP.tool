param (
    [switch]$InstallPython,
    [switch]$GetInfo,
    [switch]$RunAutomation,
    [switch]$All
)

# ==============================================================================
# MAIN CONTROLLER: Environment Setup, SUT Info, & Automation
# ==============================================================================

# 0. Check Administrator Privileges
$currentPrincipal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $currentPrincipal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Write-Warning "Please run this script as Administrator."
    Start-Process powershell -Verb RunAs -ArgumentList "-NoProfile -ExecutionPolicy Bypass -File `"$PSCommandPath`""
    exit
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# ==============================================================================
# FUNCTIONS
# ==============================================================================

function Initialize-Environment {
    Write-Host "`n=== [Part 1] Environment Setup (PowerShell & Python) ===" -ForegroundColor Cyan
    
    # 1. Update PowerShell via winget
    Write-Host "Checking for PowerShell updates via winget..." -ForegroundColor Cyan
    try {
        winget install --id Microsoft.PowerShell --accept-package-agreements --accept-source-agreements --silent
        if ($LASTEXITCODE -eq 0) { 
            Write-Host "PowerShell is up to date or updated successfully." -ForegroundColor Green 
        }
    } catch {
        Write-Host "Winget not found or failed to update PowerShell. Skipping..." -ForegroundColor Yellow
    }

    # 2. Python Check/Install
    try {
        $currentVersion = python --version 2>&1
        # Fix: Stricter regex to avoid matching "Python was not found" error message
        if ($LASTEXITCODE -eq 0 -and $currentVersion -match "Python \d+\.\d+") {
            Write-Host "Python is already installed: $currentVersion" -ForegroundColor Green
        } else {
            throw "Python not found or is the Store stub."
        }
    } catch {
        Write-Host "Python not found (or is a shortcut). Starting download..." -ForegroundColor Yellow
        $pythonUrl = "https://www.python.org/ftp/python/3.12.1/python-3.12.1-amd64.exe"
        $installerPath = "$env:TEMP\python_installer.exe"
        
        try {
            Invoke-WebRequest -Uri $pythonUrl -OutFile $installerPath
            Write-Host "Installing Python (Silent)..." -ForegroundColor Cyan
            $process = Start-Process -FilePath $installerPath -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_test=0" -Wait -PassThru
            
            if ($process.ExitCode -eq 0) { 
                Write-Host "Python installed successfully!" -ForegroundColor Green 
            } else { 
                Write-Host "Installation failed code: $($process.ExitCode)" -ForegroundColor Red
                return 
            }
        } finally {
            Remove-Item $installerPath -ErrorAction SilentlyContinue
        }
    }

    Write-Host "Refreshing environment variables..." -ForegroundColor Cyan
    $env:Path = [System.Environment]::GetEnvironmentVariable("Path","Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path","User")
    
    Write-Host "Installing automation libraries..." -ForegroundColor Cyan
    try {
        python -m pip install --upgrade pip --quiet
    $libraries = "pywinauto", "pyautogui", "opencv-python", "pillow", "beautifulsoup4"
    foreach ($lib in $libraries) {
        Write-Host "Installing $lib..."
        pip install $lib --quiet
    }
        Write-Host "Libraries installed." -ForegroundColor Green
    } catch { Write-Host "Library install warning (pip)." -ForegroundColor Yellow }
}

function Get-SUTInfo {
    Write-Host "`n=== [Part 2] Collecting SUT Information ===" -ForegroundColor Cyan
    
    # 1. Network Dump
    $tempNetFile = "$env:TEMP\NetInfo_Temp.txt"
    if (Test-Path $tempNetFile) { Remove-Item $tempNetFile -Force }
    $adapters = Get-NetAdapter | Select-Object Name, InterfaceDescription, DriverName, DriverVersion
    
    $ethKeywords = "Ethernet","GbE","LAN","I219","I225","Controller","Connection"
    $wifiKeywords = "Wi-Fi","Wireless","802.11","AX","AC","Dual Band"
    
    $etherList = $adapters | Where-Object { $n=$_.InterfaceDescription; foreach($k in $ethKeywords){if($n -match $k){return $true}} }
    $wifiList  = $adapters | Where-Object { $n=$_.InterfaceDescription; foreach($k in $wifiKeywords){if($n -match $k){return $true}} }

    foreach ($e in $etherList) { "$($e.InterfaceDescription)|$($e.DriverVersion)" | Out-File $tempNetFile -Append -Encoding ascii }
    foreach ($w in $wifiList)  { "$($w.InterfaceDescription)|$($w.DriverVersion)" | Out-File $tempNetFile -Append -Encoding ascii }

    # 2. Sys Info
    $bios = Get-CimInstance Win32_BIOS
    $cs   = Get-CimInstance Win32_ComputerSystem
    $csProd = Get-CimInstance Win32_ComputerSystemProduct
    $os   = Get-CimInstance Win32_OperatingSystem
    $cpu  = (Get-CimInstance Win32_Processor).Name
    $mem  = "{0:N2} GB" -f ((Get-CimInstance Win32_PhysicalMemory | Measure-Object -Property Capacity -Sum).Sum / 1GB)
    $gpuString = (Get-CimInstance Win32_VideoController | ForEach-Object { "$($_.Name) ($($_.DriverVersion))" }) -join " | "

    # Build ID
    $buildID = "Not Found"
    try {
        $candidates = @()
        $regBuild = Get-ItemProperty "HKLM:\SOFTWARE\Hewlett-Packard\GlobalSeries" -Name "BuildID" -ErrorAction SilentlyContinue
        if ($regBuild) { $candidates += $regBuild.BuildID }
        if ($cs.OEMStringArray) { $candidates += $cs.OEMStringArray }
        foreach ($s in $candidates) { if($s -match "BUILDID") { $buildID = $s; break } }
    } catch {}

    # 3. Parse Network
    $lanInfo = "Not Found"; $wlanInfo = "Not Found"
    if (Test-Path $tempNetFile) {
        foreach ($line in Get-Content $tempNetFile) {
            $p = $line -split "\|"; if($p.Count -lt 2){continue}
            $fmt = "$($p[0]) ($($p[1]))"
            if ($p[0] -match "Wi-Fi|Wireless|802.11") { $wlanInfo = $fmt }
            elseif ($p[0] -match "Ethernet|GbE|LAN") { $lanInfo = $fmt }
        }
    }

    # 4. Apps
    $detectedApps = [Ordered]@{}
    $hpKeywords = @("HP","Hewlett","Wolf","Sure","HotKey","Support Assistant","Client Security","BiosConfig")
    $paths = @("HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall", "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall")
    foreach ($p in $paths) {
        Get-ChildItem $p -ErrorAction SilentlyContinue | ForEach-Object {
            $prop = Get-ItemProperty $_.PSPath
            if ($prop.DisplayName -match "Driver Package") { return }
            foreach ($kw in $hpKeywords) {
                if ($prop.DisplayName -match $kw) {
                    $v = if($prop.DisplayVersion){$prop.DisplayVersion}else{"Unknown"}
                    if(-not $detectedApps.Contains($prop.DisplayName)) { $detectedApps[$prop.DisplayName] = $v }
                    break
                }
            }
        }
    }

    # Output
    $outDir = Join-Path (Split-Path -Parent $scriptDir) "hp.v"
    if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }
    $outputFile = Join-Path $outDir "SUT_Output.txt"
    $csvRows = @()
    $csvRows += [PSCustomObject]@{ Key="SUT_Name"; Value=$env:COMPUTERNAME }
    $csvRows += [PSCustomObject]@{ Key="Platform"; Value="$($csProd.Name) / $($cs.SystemSKU)" }
    $csvRows += [PSCustomObject]@{ Key="Build_ID"; Value=$buildID }
    $csvRows += [PSCustomObject]@{ Key="BIOS";     Value="$($bios.Name) ($($bios.SMBIOSBIOSVersion))" }
    $csvRows += [PSCustomObject]@{ Key="OS";       Value="$($os.Caption) - $($os.BuildNumber)" }
    $csvRows += [PSCustomObject]@{ Key="CPU";      Value=$cpu }
    $csvRows += [PSCustomObject]@{ Key="Memory";   Value=$mem }
    $csvRows += [PSCustomObject]@{ Key="GPU";      Value=$gpuString }
    $csvRows += [PSCustomObject]@{ Key="LAN";      Value=$lanInfo }
    $csvRows += [PSCustomObject]@{ Key="WLAN";     Value=$wlanInfo }
    
    $i=1
    foreach($k in $detectedApps.Keys){ $csvRows += [PSCustomObject]@{ Key="HP_App_$i"; Value="$k ($($detectedApps[$k]))" }; $i++ }
    
    $csvRows | Format-Table -AutoSize
    $csvRows | Export-Csv -Path $outputFile -NoTypeInformation -Encoding UTF8
    Write-Host "Info saved to: $outputFile" -ForegroundColor Green
}

function Run-AutomationScript {
    Write-Host "`n=== [Part 3] Running Automation Script: TG4 ===" -ForegroundColor Cyan
    $pyScript = ".\automation_runner.py"
    if (Test-Path $pyScript) {
        # Call with specific test argument
        python $pyScript --test TG4
    } else {
        Write-Warning "File '$pyScript' not found."
    }
}

function Check-HPSoftwareVersions {
    Write-Host "`n=== HP Software Version Comparison ===" -ForegroundColor Cyan
    $pyScript = ".\version_checker.py"
    if (Test-Path $pyScript) {
        python $pyScript
    } else {
        Write-Warning "File '$pyScript' not found."
    }
}

function Invoke-MPMMenu {
    $mpmPath = Join-Path $scriptDir "hp.s.mpm"
    if (-not (Test-Path $mpmPath)) {
        Write-Warning "MPM folder not found at $mpmPath"
        Pause
        return
    }

    $backMPM = $false
    do {
        Clear-Host
        Write-Host "=========================================" -ForegroundColor Yellow
        Write-Host "      MPM & BIOS Config Utility          " -ForegroundColor Yellow
        Write-Host "=========================================" -ForegroundColor Yellow
        Write-Host " 1. [Step 1] Get Original Config (BIOS -> txt)"
        Write-Host " 2. [Step 2] Get Unlock Config (Template -> txt)"
        Write-Host " 3. [Step 3] Merge Configs (Merge Data to Unlock)"
        Write-Host " 4. [Step 4] Set Config (Apply txt -> BIOS)"
        Write-Host " B. Back to Main Menu"
        Write-Host "=========================================" -ForegroundColor Yellow
        
        $mChoice = Read-Host " Select Step"
        switch ($mChoice) {
            "1" { python "$mpmPath\mpm_cli.py" get-original }
            "2" { python "$mpmPath\mpm_cli.py" get-unlock }
            "3" { python "$mpmPath\mpm_cli.py" merge; Pause }
            "4" { 
                Write-Host "WARNING: Applying BIOS config can be risky." -ForegroundColor Red
                $confirm = Read-Host "Proceed? (y/n)"
                if ($confirm -eq 'y') { python "$mpmPath\mpm_cli.py" set-unlock }
            }
            "B" { $backMPM = $true }
            "b" { $backMPM = $true }
        }
    } until ($backMPM)
}

function Show-Workflow {
    Clear-Host
    Write-Host "=========================================================" -ForegroundColor White -BackgroundColor Blue
    Write-Host "         HP SUT AutoKit v3.0 Standard Workflow           " -ForegroundColor White -BackgroundColor Blue
    Write-Host "=========================================================" -ForegroundColor White -BackgroundColor Blue
    Write-Host ""
    Write-Host " [Phase 1: Preparation (New Device)]" -ForegroundColor Cyan
    Write-Host "   1. Run Mode 1 (Environment): Setup Python/Prerequisites."
    Write-Host "   2. Run Mode 2 (MPM Utility): Unlock BIOS & Set Config."
    Write-Host "   *  Note: Re-image or DASH setup usually happens here."
    Write-Host ""
    Write-Host " [Phase 2: Documentation (Start of Test)]" -ForegroundColor Cyan
    Write-Host "   3. Run Mode 3 (SUT Info):"
    Write-Host "      - Option 1: Capture HW Specs (hp.v\SUT_Output.txt)."
    Write-Host "      - Option 2: Compare HP App Versions against HTML sources."
    Write-Host "   4. Copy findings to Web 365 Excel tracker."
    Write-Host ""
    Write-Host " [Phase 3: Execution & Debugging]" -ForegroundColor Cyan
    Write-Host "   5. Run Mode 4 (Automation): Execute TG4, TG_BIO, etc."
    Write-Host "   6. Use 'Option 0' in Mode 4 for Spot Checks:"
    Write-Host "      - Check Battery / Driver Errors / BitLocker Status."
    Write-Host ""
    Write-Host "=========================================================" -ForegroundColor White -BackgroundColor Blue
    Write-Host " Press any key to return to Main Menu..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
}

# ==============================================================================
# MENU / LOGIC
# ==============================================================================

# If arguments are passed, run in non-interactive mode (Direct Execution)
if ($InstallPython -or $GetInfo -or $RunAutomation -or $All) {
    if ($InstallPython -or $All) { Initialize-Environment }
    if ($GetInfo -or $All)       { Get-SUTInfo }
    if ($RunAutomation -or $All) { Run-AutomationScript }
    exit
}

# Interactive Main Menu
$exitScript = $false
do {
    Clear-Host
    Write-Host "=========================================" -ForegroundColor Cyan
    Write-Host "    HP SUT AutoKit v3.0 (Main Gate)      " -ForegroundColor Cyan
    Write-Host "=========================================" -ForegroundColor Cyan
    Write-Host " 0. Standard Workflow & SOP Guide"
    Write-Host " 1. Environment Maintenance (Install/Update)"
    Write-Host " 2. MPM & BIOS Config Utility"
    Write-Host " 3. SUT Information & Version Check"
    Write-Host " 4. System Diagnostics & Automation Tests"
    Write-Host " Q. Quit"
    Write-Host "=========================================" -ForegroundColor Cyan

    $gate = Read-Host " Select Mode"

    switch ($gate) {
        "0" { Show-Workflow }
        "1" { 
            # Environment Mode
            Clear-Host
            Initialize-Environment
            Write-Host "`nPress any key to return to Main Gate..."
            $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
        }
        "2" {
            Invoke-MPMMenu
        }
        "3" {
            # Info Sub-Menu
            $backInfo = $false
            do {
                Clear-Host
                Write-Host "=========================================" -ForegroundColor Green
                Write-Host "      SUT Information & Version Check    " -ForegroundColor Green
                Write-Host "=========================================" -ForegroundColor Green
                Write-Host " 1. Generate SUT Info Report (SUT_Output.txt)"
                Write-Host " 2. Compare HP App Versions (HTML Parser)"
                Write-Host " B. Back to Main Gate"
                Write-Host "=========================================" -ForegroundColor Green
                
                $iChoice = Read-Host " Select Action"
                switch ($iChoice) {
                    "1" { Get-SUTInfo; Pause }
                    "2" { Check-HPSoftwareVersions; Pause }
                    "B" { $backInfo = $true }
                    "b" { $backInfo = $true }
                    Default { Write-Warning "Invalid option."; Start-Sleep -Seconds 1 }
                }
            } until ($backInfo)
        }
        "4" {
            # Automation Mode (Sub-Menu)
            $back = $false
            do {
                Clear-Host
                Write-Host "=========================================" -ForegroundColor Green
                Write-Host "      System Diagnostics & Automation    " -ForegroundColor Green
                Write-Host "=========================================" -ForegroundColor Green
                Write-Host " 0. System Diagnostics & Info Hub (Quick Checks)"
                Write-Host " 1. UX Automation (TG4: Start/Apps/Shell)"
                Write-Host " 2. Bio Automation (TG_BIO: Windows Hello)"
                Write-Host " 3. HW Automation (TG_HK: Hotkeys/Brightness)"
                Write-Host " 4. App Automation (TG_APPS: HP App Launch)"
                Write-Host " 5. BIOS Workflow (TG_FUR: Firmware/BitLocker)"
                Write-Host " B. Back to Main Gate"
                Write-Host "=========================================" -ForegroundColor Green
                
                $subChoice = Read-Host " Select Action"
                switch ($subChoice) {
                    "0" { if(Test-Path ".\quick_diag.ps1"){ & ".\quick_diag.ps1" } else { Write-Warning "quick_diag.ps1 not found." }; Pause }
                    "1" { Run-AutomationScript; Pause }
                    "2" { Write-Host "`n=== Launching TG_BIO ===" -ForegroundColor Cyan; if(Test-Path $pyScript){python $pyScript --test TG_BIO}; Pause }
                    "3" { Write-Host "`n=== Launching TG_HK ===" -ForegroundColor Cyan; if(Test-Path $pyScript){python $pyScript --test TG_HK}; Pause }
                    "4" { Write-Host "`n=== Launching TG_APPS ===" -ForegroundColor Cyan; if(Test-Path $pyScript){python $pyScript --test TG_APPS}; Pause }
                    "5" { Write-Host "`n=== Launching TG_FUR ===" -ForegroundColor Cyan; if(Test-Path $pyScript){python $pyScript --test TG_FUR}; Pause }
                    "B" { $back = $true }
                    "b" { $back = $true }
                    Default { Write-Warning "Invalid option."; Start-Sleep -Seconds 1 }
                }
            } until ($back)
        }
        "Q" { $exitScript = $true }
        "q" { $exitScript = $true }
        Default { Write-Warning "Invalid option."; Start-Sleep -Seconds 1 }
    }
} until ($exitScript)