import os
import sys
import re
from typing import List, Dict, Tuple
from utils import SystemUtils, Diagnostics, ProjectConfig

class AutomationRunner:
    def __init__(self, testcase_paths: List[str]):
        self.testcase_paths = testcase_paths
        self.test_items = []
        self.automation_map = {
            "Yellow Bang": ("Check Drivers", Diagnostics.check_drivers),
            "Ping": ("Network Ping", Diagnostics.check_network_ping),
            "Battery": ("Battery Check", Diagnostics.check_battery),
            "BitLocker": ("BitLocker Check", Diagnostics.check_bitlocker),
            "HP Apps": ("HP Apps Check", self.check_hp_apps),
            "OS Function": ("OS Info", self.check_os_info),
            "Adapter": ("Network Adapters", self.check_network_adapters),
            "USB": ("USB Check", self.check_usb),
            "Camera": ("Camera Check", self.check_camera),
            "Audio": ("Audio Check", self.check_audio),
            "Disk": ("Disk Usage", self.check_disk),
            "Memory": ("Memory Check", self.check_memory)
        }

    def check_network_adapters(self):
        # Returns raw text, need to parse for better detail
        res = SystemUtils.run_powershell("Get-NetAdapter | Select-Object Name, Status, LinkSpeed | key=value")
        # Simplistic parsing or just return as is but prefixed
        if "Up" in res:
            return f"PASS  | Network Adapters found active.\n      Details: {res.strip()}"
        return f"FAIL  | No active network adapters found.\n      Output: {res.strip()}"

    def check_usb(self):
        # Get count
        val = SystemUtils.run_powershell("Get-PnpDevice -Class USB | Where-Object { $_.Status -eq 'OK' } | Measure-Object | Select-Object -ExpandProperty Count")
        try:
            count = int(float(val.strip()))
            if count > 0:
                return f"PASS  | USB Devices Check. Found {count} active devices."
            return f"FAIL  | No USB devices found (Count=0)."
        except:
            return f"FAIL  | Error checking USB devices. Output: {val}"

    def check_camera(self):
        res = SystemUtils.run_powershell("Get-PnpDevice -Class Camera -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq 'OK' } | Select-Object FriendlyName")
        if res and len(res.strip()) > 0:
            return f"PASS  | Camera detected.\n      Details: {res.strip()}"
        return "FAIL  | No Camera devices found."

    def check_audio(self):
        res = SystemUtils.run_powershell("Get-PnpDevice -Class AudioEndpoint -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq 'OK' } | Select-Object FriendlyName")
        if res and len(res.strip()) > 0:
            return f"PASS  | Audio Endpoints detected.\n      Details: {res.strip()}"
        return "FAIL  | No Audio Endpoints found."

    def check_disk(self):
        res = SystemUtils.run_powershell("Get-Volume | Select-Object DriveLetter, FileSystemLabel, SizeRemaining, Size")
        if "C" in res:
            return f"PASS  | Disk Volumes Info retrieved.\n      Details: {res.strip()}"
        return f"FAIL  | Could not retrieve Disk Info.\n      Output: {res}"

    def check_memory(self):
        res = SystemUtils.run_powershell("Get-CimInstance Win32_PhysicalMemory | Select-Object Capacity, Speed, Manufacturer")
        if res and len(res.strip()) > 0:
            return f"PASS  | Memory Modules detected.\n      Details: {res.strip()}"
        return "FAIL  | No Memory info returned."

    def check_hp_apps(self):
        info = SystemUtils.get_sut_info()
        apps = info.get("HP_Apps", [])
        if apps:
            return f"PASS  | HP Apps Check. Found {len(apps)} apps.\n      List: {', '.join(apps[:5])}..."
        return "FAIL  | No HP Apps found."

    def check_os_info(self):
        info = SystemUtils.get_sut_info()
        os_name = info.get('OS', 'Unknown')
        if os_name != 'Unknown':
            return f"PASS  | OS Detected: {os_name}"
        return "FAIL  | Could not detect OS version."

    # Wrappers for Utils/Diagnostics to ensure consistent format
    def wrap_diag_drivers(self):
        res = Diagnostics.check_drivers()
        if "PASS" in res:
            return "PASS  | Driver Check. No yellow bangs found."
        return f"FAIL  | Driver Issues Found.\n      {res}"

    def wrap_diag_ping(self):
        res = Diagnostics.check_network_ping()
        if "PASS" in res:
            return f"PASS  | {res.replace('PASS:', '').strip()}"
        return f"FAIL  | {res.replace('FAIL:', '').strip()}"

    def wrap_diag_battery(self):
        res = Diagnostics.check_battery()
        if "No Battery" in res:
            return "WARN  | No Battery Detected (Desktop?)."
        return f"PASS  | Battery Status: {res.strip()}"

    def wrap_diag_bitlocker(self):
        res = Diagnostics.check_bitlocker()
        return f"INFO  | BitLocker Status:\n      {res.strip()}"

    def scan_coverage(self):
        """
        Scans all provided testcase files.
        """
        self.test_items = []
        
        # Update mapping to use wrappers
        self.automation_map = {
            "Yellow Bang": ("Check Drivers", self.wrap_diag_drivers),
            "Ping": ("Network Ping", self.wrap_diag_ping),
            "Battery": ("Battery Check", self.wrap_diag_battery),
            "BitLocker": ("BitLocker Check", self.wrap_diag_bitlocker),
            "HP Apps": ("HP Apps Check", self.check_hp_apps),
            "OS Function": ("OS Info", self.check_os_info),
            "Adapter": ("Network Adapters", self.check_network_adapters),
            "USB": ("USB Check", self.check_usb),
            "Camera": ("Camera Check", self.check_camera),
            "Audio": ("Audio Check", self.check_audio),
            "Disk": ("Disk Usage", self.check_disk),
            "Memory": ("Memory Check", self.check_memory)
        }

        for path in self.testcase_paths:
            if not os.path.exists(path):
                continue

            filename = os.path.basename(path)
            with open(path, 'r', encoding='utf-8', errors='ignore') as f:
                lines = f.readlines()
            
            for i, line in enumerate(lines):
                line = line.strip()
                if not line or line.startswith("▼") or line.startswith("Step"):
                    continue
                
                status = "Manual"
                auto_func = None
                feature_name = "Unknown"

                for key, (name, func) in self.automation_map.items():
                    if key.lower() in line.lower():
                        status = "Auto"
                        auto_func = func
                        feature_name = name
                        break
                
                self.test_items.append({
                    "file": filename,
                    "line_no": i + 1,
                    "content": line[:100] + "..." if len(line) > 100 else line,
                    "status": status,
                    "feature": feature_name,
                    "func": auto_func
                })

        # Calculate Stats
        total_items = len(self.test_items)
        auto_items = len([x for x in self.test_items if x["status"] == "Auto"])
        coverage = (auto_items / total_items * 100) if total_items > 0 else 0
        
        return {
            "total": total_items,
            "auto": auto_items,
            "coverage": coverage,
            "items": self.test_items
        }

    def run_automation(self):
        results = []
        scan_data = self.scan_coverage()
        
        if isinstance(scan_data, str):
            return scan_data

        results.append(f"=== Automation Report ===")
        results.append(f"Files: {', '.join([os.path.basename(p) for p in self.testcase_paths])}")
        results.append(f"Total: {scan_data['total']} | Auto: {scan_data['auto']} | Cov: {scan_data['coverage']:.1f}%")
        results.append("="*60)
        
        if scan_data['auto'] == 0:
             results.append("No automated tests found in selected files.")

        for item in scan_data["items"]:
            if item["status"] == "Auto":
                func = item["func"]
                feature = item["feature"]
                try:
                    res = func()
                    # Formatting
                    results.append(f"TEST: {feature} (Line {item['line_no']})")
                    results.append(f"{res}")
                    results.append("-" * 40)
                except Exception as e:
                    results.append(f"TEST: {feature} (Line {item['line_no']})")
                    results.append(f"FAIL  | Exception Occurred: {e}")
                    results.append("-" * 40)
        
        return "\n".join(results)

if __name__ == "__main__":
    runner = AutomationRunner(["testcase.txt"])
    print(runner.run_automation())
