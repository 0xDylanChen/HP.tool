import subprocess
import sys

def run_powershell(cmd):
    """Executes a PowerShell command and returns the output string."""
    try:
        # -NoProfile -ExecutionPolicy Bypass to ensure it runs
        full_cmd = ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", cmd]
        print(f"Running command: {full_cmd}")
        result = subprocess.run(full_cmd, capture_output=True, text=True)
        print("--- STDOUT ---")
        print(result.stdout)
        print("--- STDERR ---")
        print(result.stderr)
        return result.stdout.strip()
    except Exception as e:
        print(f"Exception: {e}")
        return str(e)

apps_ps = """
$hpKeywords = 'HP|Hewlett|Wolf|Sure|HotKey|Support Assistant|Client Security'
$paths = 'HKLM:\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*', 'HKLM:\\SOFTWARE\\WOW6432Node\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\*'

$list = Get-ItemProperty -Path $paths -ErrorAction SilentlyContinue | 
    Where-Object { $_.DisplayName -match $hpKeywords } |
    ForEach-Object { "$($_.DisplayName)|$($_.DisplayVersion)" }    

if ($list) { $list -join ";" } else { "NO_MATCHES_FOUND" }
"""

print("Executing PowerShell script...")
output = run_powershell(apps_ps)
print(f"Final Output: {output}")
