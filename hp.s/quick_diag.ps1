function Show-Header {
    param($Title)
    Write-Host "`n=== $Title ===" -ForegroundColor Cyan
}

function Check-DeviceErrors {
    Show-Header "Device Manager (Yellow Bang Check)"
    # ConfigManagerErrorCode 0 means "This device is working properly."
    # We look for anything NOT 0.
    $errorDevs = Get-PnpDevice | Where-Object { $_.ConfigManagerErrorCode -ne 0 }

    if ($errorDevs) {
        Write-Host "FOUND ISSUES: The following devices have errors (Yellow Bangs):" -ForegroundColor Red
        $errorDevs | Format-Table -Property FriendlyName, InstanceId, ConfigManagerErrorCode -AutoSize
    } else {
        Write-Host "PASS: No devices with errors found (No Yellow Bangs)." -ForegroundColor Green
    }
}

function Check-Network {
    Show-Header "Network Connectivity"
    
    # 1. Check Adapters
    $adapters = Get-NetAdapter | Where-Object { $_.Status -eq "Up" }
    if ($adapters) {
        Write-Host "Active Adapters:"
        $adapters | Format-Table -Property Name, InterfaceDescription, Status, LinkSpeed -AutoSize
    } else {
        Write-Host "WARNING: No active network adapters found!" -ForegroundColor Yellow
    }

    # 2. Ping Test (Test Case 6 reference)
    $target = "internetbeacon.msedge.net" # Common MS connectivity check
    Write-Host "Ping Test ($target): " -NoNewline
    try {
        $ping = Test-Connection -ComputerName $target -Count 1 -ErrorAction Stop
        if ($ping.Status -eq "Success") {
            Write-Host "SUCCESS ($($ping.ResponseTime)ms)" -ForegroundColor Green
        } else {
            Write-Host "FAILED" -ForegroundColor Red
        }
    } catch {
        Write-Host "FAILED (No Connection)" -ForegroundColor Red
    }
}

function Check-PowerStatus {
    Show-Header "Power & Battery Status"
    
    # Battery Info
    $battery = Get-CimInstance -ClassName Win32_Battery -ErrorAction SilentlyContinue
    if ($battery) {
        $statusMap = @{1="Discharging"; 2="AC/Charging"; 3="Fully Charged"; 4="Low"; 5="Critical"}
        $batStatus = $statusMap[[int]$battery.BatteryStatus]
        
        Write-Host "Battery Level:   " -NoNewline; Write-Host "$($battery.EstimatedChargeRemaining)%" -ForegroundColor Green
        Write-Host "Battery Status:  $batStatus"
    } else {
        Write-Host "No Battery Detected (Desktop?)" -ForegroundColor DarkGray
    }
}

function Check-HPSoftwareVersions {
    Show-Header "HP Software Version Mismatch Check"
    $scriptPath = Resolve-Path "$PSScriptRoot\version_checker.py"
    if (Test-Path $scriptPath) {
        Write-Host "Launching Python comparison tool..." -ForegroundColor Gray
        python $scriptPath
    } else {
        Write-Host "Error: Cannot find $scriptPath" -ForegroundColor Red
    }
}

function Check-BitLocker {
    Show-Header "BitLocker Status (C: Drive)"
    try {
        $status = Get-BitLockerVolume -MountPoint "C:" -ErrorAction Stop
        
        $color = if ($status.VolumeStatus -eq "FullyDecrypted") { "Green" } 
                 elseif ($status.VolumeStatus -eq "FullyEncrypted") { "Yellow" }
                 else { "Red" }
        
        Write-Host "Status:      " -NoNewline; Write-Host $status.VolumeStatus -ForegroundColor $color
        Write-Host "Protection:  " -NoNewline; Write-Host $status.ProtectionStatus
        Write-Host "Percentage:  $($status.EncryptionPercentage)%"
        Write-Host "Key Protectors:"
        foreach ($p in $status.KeyProtector) {
            Write-Host "  - $($p.KeyProtectorType)" -ForegroundColor DarkGray
        }
    } catch {
        Write-Host "Error checking BitLocker (Admin rights needed?)" -ForegroundColor Red
        manage-bde -status C:
    }
}

function Check-Biometrics {
    Show-Header "Biometrics & IR Camera Check"
    $devs = Get-PnpDevice | Where-Object { 
        $_.Class -eq "Biometric" -or 
        ($_.Class -eq "Camera" -and $_.FriendlyName -match "IR") 
    }

    if ($devs) {
        $devs | Format-Table -Property FriendlyName, Class, Status -AutoSize
        
        if ($devs | Where-Object {$_.FriendlyName -match "IR"}) {
            Write-Host "[RESULT] IR Camera Detected: YES" -ForegroundColor Green
        } else {
            Write-Host "[RESULT] IR Camera Detected: NO" -ForegroundColor Yellow
        }
    } else {
        Write-Host "No Biometric or IR devices found." -ForegroundColor Yellow
    }
}

function Check-SecurityBoot {
    Show-Header "Security Features (Secure Boot / TPM)"
    # Secure Boot
    try {
        $sb = Confirm-SecureBootUEFI
        Write-Host "Secure Boot: " -NoNewline
        if ($sb) { Write-Host "ENABLED" -ForegroundColor Green } else { Write-Host "DISABLED" -ForegroundColor Red }
    } catch {
        Write-Host "Secure Boot: Unknown (Error or Legacy BIOS)" -ForegroundColor DarkGray
    }

    # TPM
    try {
        $tpm = Get-Tpm
        Write-Host "TPM Ready:   " -NoNewline
        if ($tpm.TpmReady) { Write-Host "YES" -ForegroundColor Green } else { Write-Host "NO" -ForegroundColor Red }
    } catch {
        Write-Host "TPM Check Failed" -ForegroundColor DarkGray
    }
}

function Get-SUTInfo {
    Show-Header "Collecting SUT Information"
    
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
    $outDir = Join-Path (Split-Path -Parent $PSScriptRoot) "hp.v"
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

function Check-FullSecurity {
    Check-BitLocker
    Check-SecurityBoot
}

# ==============================================================================
# INTERACTIVE MENU
# ==============================================================================

do {
    Clear-Host
    Write-Host "=========================================" -ForegroundColor Magenta
    Write-Host "   HP System Diagnostics (Health Check)  " -ForegroundColor Magenta
    Write-Host "=========================================" -ForegroundColor Magenta
    Write-Host " 1. Run ALL Health Checks" -ForegroundColor Cyan
    Write-Host ""
    Write-Host " [INDIVIDUAL CHECKS]" -ForegroundColor Gray
    Write-Host " 2. Check Device Manager (Drivers)"
    Write-Host " 3. Check Network (Adapters & Ping)"
    Write-Host " 4. Check Power (Battery Status)"
    Write-Host " 5. Check Security (BitLocker/TPM/SecureBoot)"
    Write-Host " 6. Check Biometrics (IR/Fingerprint)"
    Write-Host " Q. Quit / Return"
    Write-Host "=========================================" -ForegroundColor Magenta

    $choice = Read-Host " Select Action"

    switch ($choice) {
        "1" { 
            Check-DeviceErrors
            Check-Network
            Check-PowerStatus
            Check-FullSecurity
            Check-Biometrics
            Pause 
        }
        "2" { Check-DeviceErrors; Pause }
        "3" { Check-Network; Pause }
        "4" { Check-PowerStatus; Pause }
        "5" { Check-FullSecurity; Pause }
        "6" { Check-Biometrics; Pause }
        "Q" { exit }
        "q" { exit }
        Default { Write-Warning "Invalid option."; Start-Sleep -Seconds 1 }
    }
} while ($true)
