import os
import sys
import subprocess
import platform
import json
import ctypes
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Union

class ProjectConfig:
    """
    Central Configuration for Project Paths and Constants.
    """
    ROOT: Path = Path(__file__).parent.resolve()
    SCRIPTS_DIR: Path = ROOT / "hp.s"
    OUTPUT_DIR: Path = ROOT / "hp.v"
    ARCHIVE_DIR: Path = ROOT / "bin"
    MPM_DIR: Path = SCRIPTS_DIR / "hp.s.mpm"
    VERSION_MAPPING_FILE: Path = SCRIPTS_DIR / "version_mapping.txt"

    @classmethod
    def ensure_dirs(cls):
        """Ensure necessary directories exist."""
        cls.OUTPUT_DIR.mkdir(exist_ok=True)
        cls.ARCHIVE_DIR.mkdir(exist_ok=True)

class SystemUtils:
    @staticmethod
    def is_admin() -> bool:
        """Check if the current process has administrative privileges."""
        try:
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        except AttributeError:
            return False

    @staticmethod
    def elevate() -> None:
        """Attempts to re-launch the script with admin privileges."""
        params = " ".join([f'"{arg}"' for arg in sys.argv])
        ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, f'"{sys.argv[0]}" {params}', None, 1)
        sys.exit()

    @staticmethod
    def setup_environment() -> str:
        """Checks and installs missing requirements from requirements.txt."""
        req_file = ProjectConfig.ROOT / "requirements.txt"
        if not req_file.exists():
            return "requirements.txt not found."
        
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req_file), "--quiet"])
            return "Environment ready."
        except Exception as e:
            return f"Pip install failed: {e}"

    @staticmethod
    def run_powershell(cmd: str) -> str:
        """
        Executes a PowerShell command and returns the output string.
        
        Args:
            cmd (str): The PowerShell command to execute.
            
        Returns:
            str: The stdout from the command, or an error message.
        """
        try:
            # -NoProfile -ExecutionPolicy Bypass to ensure it runs
            full_cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd]
            
            # Hide window on Windows
            creationflags = 0
            if os.name == 'nt':
                creationflags = subprocess.CREATE_NO_WINDOW
                
            result = subprocess.run(
                full_cmd, 
                capture_output=True, 
                text=True, 
                creationflags=creationflags
            )
            return result.stdout.strip()
        except Exception as e:
            return f"Error executing PowerShell: {str(e)}"

    @staticmethod
    def get_sut_info() -> Dict[str, Any]:
        """
        Collects system information (OS, CPU, Memory, BIOS, Network, Apps).
        
        Returns:
            Dict[str, Any]: A dictionary containing collected system info.
        """
        info = {}
        info['SUT_Name'] = platform.node()
        info['OS'] = SystemUtils.run_powershell("(Get-CimInstance Win32_OperatingSystem).Caption + ' - ' + (Get-CimInstance Win32_OperatingSystem).BuildNumber")
        info['CPU'] = SystemUtils.run_powershell("(Get-CimInstance Win32_Processor).Name")
        
        # Memory
        mem_raw = SystemUtils.run_powershell("(Get-CimInstance Win32_PhysicalMemory | Measure-Object -Property Capacity -Sum).Sum / 1GB")
        try:
            info['Memory'] = f"{float(mem_raw):.2f} GB"
        except (ValueError, TypeError):
            info['Memory'] = "Unknown"

        # BIOS
        bios_name = SystemUtils.run_powershell("(Get-CimInstance Win32_BIOS).Name")
        bios_ver = SystemUtils.run_powershell("(Get-CimInstance Win32_BIOS).SMBIOSBIOSVersion")
        info['BIOS'] = f"{bios_name} ({bios_ver})"
        
        # Platform & BuildID
        prod_name = SystemUtils.run_powershell("(Get-CimInstance Win32_ComputerSystemProduct).Name")
        sku = SystemUtils.run_powershell("(Get-CimInstance Win32_ComputerSystem).SystemSKU")
        info['Platform'] = f"{prod_name} / {sku}"

        # Attempt to find BuildID in Registry or OEMStrings
        bid_ps = """
        $bid = "Not Found"
        $reg = Get-ItemProperty 'HKLM:\\SOFTWARE\\Hewlett-Packard\\GlobalSeries' -Name 'BuildID' -ErrorAction SilentlyContinue
        if($reg){ $bid = $reg.BuildID }
        else {
            $cs = Get-CimInstance Win32_ComputerSystem
            foreach($s in $cs.OEMStringArray){ if($s -match 'BUILDID'){ $bid = $s; break } }
        }
        $bid
        """
        info['Build_ID'] = SystemUtils.run_powershell(bid_ps)

        # GPU
        info['GPU'] = SystemUtils.run_powershell("(Get-CimInstance Win32_VideoController | ForEach-Object { \"$($_.Name) ($($_.DriverVersion))\" }) -join ' | '")

        # Network
        net_ps = """
        $adapters = Get-NetAdapter | Select-Object Name, InterfaceDescription, DriverVersion
        $eth = $adapters | Where-Object { $_.InterfaceDescription -match 'Ethernet|GbE|LAN' } | Select-Object -First 1
        $wifi = $adapters | Where-Object { $_.InterfaceDescription -match 'Wi-Fi|Wireless' } | Select-Object -First 1
        $e_out = if($eth){ \"$($eth.InterfaceDescription) ($($eth.DriverVersion))\" } else { \"Not Found\" }
        $w_out = if($wifi){ \"$($wifi.InterfaceDescription) ($($wifi.DriverVersion))\" } else { \"Not Found\" }
        \"$e_out|$w_out\"
        """
        net_res = SystemUtils.run_powershell(net_ps)
        if "|" in net_res:
            info['LAN'], info['WLAN'] = net_res.split("|")
        else:
            info['LAN'] = "Not Found"
            info['WLAN'] = "Not Found"

        # HP Apps (Deep Search)
        apps_ps = """
        $hpKeywords = 'HP|Hewlett|Wolf|Sure|HotKey|Support Assistant|Client Security'
        $paths = 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*', 'HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*'
        
        $list = Get-ItemProperty -Path $paths -ErrorAction SilentlyContinue | 
            Where-Object { $_.DisplayName -match $hpKeywords } |
            ForEach-Object { "$($_.DisplayName)|$($_.DisplayVersion)" }
            
        if ($list) { $list -join ";" } else { "" }
        """
        apps_raw = SystemUtils.run_powershell(apps_ps)
        info['HP_Apps'] = [a.replace("|", " (") + ")" for a in apps_raw.split(";") if a]

        return info

    @staticmethod
    def save_sut_info(info: Dict[str, Any], filepath: Union[str, Path]) -> Union[bool, str]:
        """Save collected info to a CSV file."""
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write("Key,Value\n")
                for k, v in info.items():
                    if k == 'HP_Apps':
                        for i, app in enumerate(v, 1):
                            f.write(f"HP_App_{i},{app}\n")
                    else:
                        f.write(f"{k},{v}\n")
            return True
        except Exception as e:
            return f"Error saving file: {e}"

class Diagnostics:
    @staticmethod
    def check_drivers() -> str:
        """Checks for devices with errors (Yellow Bangs)."""
        cmd = "Get-PnpDevice | Where-Object { $_.ConfigManagerErrorCode -ne 0 } | Select-Object FriendlyName, InstanceId, ConfigManagerErrorCode | ConvertTo-Json"
        out = SystemUtils.run_powershell(cmd)
        if not out: return "PASS: No driver errors found."
        return f"ISSUES FOUND:\n{out}"

    @staticmethod
    def check_network_ping(target: str = "internetbeacon.msedge.net") -> str:
        """
        Pings a target host.
        """
        # Note: os.system is simple/robust for this basic check
        response = os.system(f"ping -n 1 {target} > nul 2>&1")
        if response == 0:
            return f"PASS: Ping to {target} successful."
        else:
            return f"FAIL: Cannot reach {target}."

    @staticmethod
    def check_battery() -> str:
        cmd = """
        $b = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue
        if($b){ \"$($b.EstimatedChargeRemaining)%|$(switch($b.BatteryStatus){1{'Discharging'} 2{'AC/Charging'} 3{'Full'} 4{'Low'} 5{'Critical'} default{'Unknown'}})\" } 
        else { \"No Battery\" }
        """
        return SystemUtils.run_powershell(cmd)

    @staticmethod
    def check_bitlocker() -> str:
        cmd = "Get-BitLockerVolume -MountPoint 'C:' | Select-Object VolumeStatus, ProtectionStatus, EncryptionPercentage | ConvertTo-Json"
        out = SystemUtils.run_powershell(cmd)
        try:
            data = json.loads(out)
            return f"Status: {data.get('VolumeStatus')}, Protection: {data.get('ProtectionStatus')}, Encrypted: {data.get('EncryptionPercentage')}%"
        except (json.JSONDecodeError, TypeError):
            return "Error checking BitLocker (Admin rights required?)"

class MPMUtils:
    CLI_SCRIPT = "mpm_cli.py"
    
    @classmethod
    def run_mpm_cli(cls, command: str) -> str:
        """Runs the MPM CLI script with the given command."""
        script_path = ProjectConfig.MPM_DIR / cls.CLI_SCRIPT
        
        if not script_path.exists():
            return f"Error: Script {cls.CLI_SCRIPT} not found at {script_path}"
        
        try:
            cmd = [sys.executable, str(script_path), command]
            
            # Use CREATE_NEW_CONSOLE for external tools that might need interaction
            # or separate elevation prompts.
            subprocess.Popen(cmd, cwd=str(ProjectConfig.MPM_DIR), creationflags=subprocess.CREATE_NEW_CONSOLE)
            return f"Launched {command}..."
            
        except Exception as e:
            return f"Execution Error: {e}"

    @classmethod
    def get_original_config(cls):
        return cls.run_mpm_cli("get-original")

    @classmethod
    def get_unlock_config(cls):
        return cls.run_mpm_cli("get-unlock")

    @classmethod
    def merge_configs(cls):
        return cls.run_mpm_cli("merge")

    @classmethod
    def set_unlock_config(cls):
        return cls.run_mpm_cli("set-unlock")