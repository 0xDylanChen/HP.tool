MPM CONFIG WORKFLOW (ENTERPRISE STANDARD)

NAME
mpm-cli - Unified command-line interface for HP BIOS Configuration management.

SYNOPSIS
python mpm_cli.py <COMMAND>

COMMANDS
  get-original   Retrieve the current BIOS configuration to Config_original.txt
  get-unlock     Retrieve the configuration to Config_unlock.txt
  merge          Merge original settings into the unlock configuration
  set-unlock     Apply the unlocked configuration to the BIOS

DESCRIPTION
This utility manages the lifecycle of HP BIOS configuration during the Manufacturing
Programming Mode (MPM) unlock process. It encapsulates business logic for
preserving critical system identity fields (Serial, SKU, MAC, etc.) while allowing
configuration updates.

REQUIREMENTS
- Administrative Privileges (Script will auto-elevate if needed)
- BiosConfigUtility64.exe (Must be present in the same directory)

WORKFLOW
1. Acquire Original Config:
   > python mpm_cli.py get-original

2. (Manual Step) Perform MPM Unlock on the device.

3. Acquire Unlock Config:
   > python mpm_cli.py get-unlock

4. Merge Configurations:
   > python mpm_cli.py merge
   
   *This step automatically applies business rules to copy Serial, SKU, MAC,
    and Feature Byte from Original -> Unlock config.*

5. Apply Configuration:
   > python mpm_cli.py set-unlock

EXIT CODES
0   - Success
1   - General Error
Others - BCU specific error codes

FILES
mpm_core.py - Core business logic and BCU wrapper class
mpm_cli.py  - CLI entry point
Config_original.txt - Backup of original state
Config_unlock.txt   - Working configuration file