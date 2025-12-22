"""
MPM Core Logic Module
---------------------
Encapsulates business logic for HP BIOS Configuration Utility (BCU) operations
and configuration merging strategies.

Standards:
- Error Handling: Raises exceptions rather than printing.
- Type Hinting: Uses Python standard typing.
- Separation of Concerns: Logic is separated from UI/CLI.
"""

import os
import sys
import re
import subprocess
import ctypes
from typing import Dict, List, Tuple, Optional

class MPMError(Exception):
    """Base exception for MPM related errors."""
    pass

class AdminRequiredError(MPMError):
    """Raised when operation requires admin privileges but current user is not admin."""
    pass

class BCUExecutionError(MPMError):
    """Raised when BiosConfigUtility returns a failure code."""
    pass

class FileNotFoundError(MPMError):
    """Raised when a required config file is missing."""
    pass

class MPMManager:
    """
    Manager class for handling HP BIOS Configuration tasks.
    """
    
    # Constants
    BCU_EXE_NAME = "BiosConfigUtility64.exe"
    CONFIG_ORIGINAL = "Config_original.txt"
    CONFIG_UNLOCK = "Config_unlock.txt"
    
    # Business Rules: Fields to manage during merge
    FIELDS_TO_COPY = [
        "Product Name", "Serial Number", "SKU Number", "System board CT number",
        "Feature Byte", "Host Based MAC Address", "Cirrus Discrete Amp Calibration Data",
        "HBMA Factory MAC Address", "HBMA System MAC Address", "MPM Counter"
    ]
    
    MAC_FIELDS = ["HBMA Factory MAC Address", "HBMA System MAC Address"]

    def __init__(self, working_dir: Optional[str] = None):
        """
        Initialize the MPM Manager. 
        
        Args:
            working_dir: The directory containing BCU exe and config files. 
                         Defaults to the directory of this script.
        """
        if working_dir:
            self.base_dir = working_dir
        else:
            self.base_dir = os.path.dirname(os.path.abspath(__file__))
            
        self.bcu_path = os.path.join(self.base_dir, self.BCU_EXE_NAME)
        self.config_orig_path = os.path.join(self.base_dir, self.CONFIG_ORIGINAL)
        self.config_unlock_path = os.path.join(self.base_dir, self.CONFIG_UNLOCK)

    def _check_admin(self):
        """Checks if the script is running with administrative privileges."""
        try:
            is_admin = ctypes.windll.shell32.IsUserAnAdmin()
        except:
            is_admin = False
            
        if not is_admin:
            raise AdminRequiredError("This operation requires Administrator privileges.")

    def _run_bcu_command(self, args: List[str]) -> str:
        """
        Executes a command against the BCU executable.
        
        Returns:
            The stdout/stderr output.
        """
        if not os.path.exists(self.bcu_path):
            raise FileNotFoundError(f"BCU Executable not found at: {self.bcu_path}")
        
        cmd = [self.bcu_path] + args
        try:
            # We assume check_admin is called before high-level operations, 
            # but BCU itself might fail if not elevated.
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                encoding='utf-8', 
                errors='replace'
            )
            # Note: BCU uses various exit codes. We log output regardless.
            output = result.stdout + "\n" + result.stderr
            return output
        except Exception as e:
            raise BCUExecutionError(f"Failed to execute BCU: {str(e)}")

    def get_original_config(self) -> str:
        """Retrieves the current BIOS configuration."""
        self._check_admin()
        return self._run_bcu_command([f"--getconfig:{self.config_orig_path}"])

    def get_unlock_config(self) -> str:
        """Retrieves the configuration (usually after manual MPM unlock)."""
        self._check_admin()
        return self._run_bcu_command([f"--getconfig:{self.config_unlock_path}"])

    def set_unlock_config(self) -> str:
        """Applies the modified configuration back to the BIOS."""
        self._check_admin()
        if not os.path.exists(self.config_unlock_path):
            raise FileNotFoundError(f"Config file not found: {self.config_unlock_path}")
            
        return self._run_bcu_command([f"--setconfig:{self.config_unlock_path}"])

    def merge_configs(self) -> str:
        """
        Merges data from original config into the unlock config based on business rules.
        """
        if not os.path.exists(self.config_orig_path):
            raise FileNotFoundError("Config_original.txt is missing.")
        if not os.path.exists(self.config_unlock_path):
            raise FileNotFoundError("Config_unlock.txt is missing.")

        orig_data, _ = self._parse_bcu_file(self.config_orig_path)
        unlock_data, unlock_lines = self._parse_bcu_file(self.config_unlock_path)
        
        # Apply Merging Logic
        updates_made = 0
        for key in self.FIELDS_TO_COPY:
            if key not in orig_data:
                continue
            
            orig_val = orig_data[key]
            should_update = False
            
            if key in self.MAC_FIELDS:
                # MAC Logic: Update if missing in unlock OR if unlock has zeroed MAC
                unlock_val = unlock_data.get(key, "")
                if key not in unlock_data or self._is_zero_mac(unlock_val):
                    should_update = True
            else:
                # Standard Logic: Update if missing or empty in unlock
                if key not in unlock_data or not unlock_data[key]:
                    should_update = True
            
            if should_update:
                unlock_data[key] = orig_val
                updates_made += 1

        # Reconstruct file content to preserve formatting
        new_content = self._rebuild_file_content(unlock_lines, unlock_data)
        
        try:
            with open(self.config_unlock_path, 'w', encoding='utf-8') as f:
                f.writelines(new_content)
        except IOError as e:
            raise MPMError(f"Failed to write config file: {e}")
            
        return f"Merge completed. {updates_made} fields updated."

    def _parse_bcu_file(self, filepath: str) -> Tuple[Dict[str, str], List[str]]:
        """Parses a BCU text file into a dictionary and preserves original lines."""
        data = {}
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            lines = f.readlines()
        
        for i, line in enumerate(lines):
            key = line.strip()
            # Valid keys are not empty and don't start with ;
            if not key or key.startswith(";"):
                continue
            
            # Check if next line is a value (indented)
            if i + 1 < len(lines):
                next_line = lines[i+1]
                if next_line.startswith("\t") or next_line.startswith("    "):
                    data[key] = next_line.strip()
        
        return data, lines

    def _rebuild_file_content(self, original_lines: List[str], data_map: Dict[str, str]) -> List[str]:
        """Rebuilds the file lines using the updated data map."""
        new_lines = []
        skip_next = False
        
        for i, line in enumerate(original_lines):
            if skip_next:
                skip_next = False
                continue
            
            trim = line.strip()
            # If this line is a known key, write it and its value
            if trim in self.FIELDS_TO_COPY:
                new_lines.append(line) # Keep the key line
                val = data_map.get(trim, "")
                new_lines.append(f"\t{val}\n")
                
                # Check if we need to skip the *original* value line
                if i + 1 < len(original_lines):
                    next_l = original_lines[i+1]
                    if next_l.startswith("\t") or next_l.startswith("    "):
                        skip_next = True
            else:
                new_lines.append(line)
                
        return new_lines

    def _is_zero_mac(self, val: str) -> bool:
        """Determines if a MAC address string is effectively zero/empty."""
        if not val or not val.strip():
            return True
        clean = re.sub(r"[:\- ]", "", val)
        return bool(re.match(r"^[0]+$", clean))
