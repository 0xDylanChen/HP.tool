# HP Automation Script Suite

This project provides an automated environment for system configuration, information gathering, and UX testing on HP SUTs (System Under Test).

## 📂 Directory Structure

```text
C:\HP_Script\
├── script_main.bat           # [ENTRY POINT] Main launcher script (Run as Admin) 
├── setup_environment.ps1     # [CORE] PowerShell controller for setup & execution
├── automation_script.py      # [CORE] Python automation logic (PyWinAuto/PyAutoGUI)
├── bin\                      # Legacy/Backup scripts
└── SUT_Output.txt            # Generated report containing system info
```

## 🚀 Quick Start

### 1. Launch the Controller
Simply double-click **`script_main.bat`**.
*   It will automatically check for Administrator privileges.
*   It launches the **Main Gate** menu.

### 2. Interactive Modes
The script features a two-level menu:

*   **Mode 1: Environment Maintenance**
    *   Installs/Updates PowerShell via Winget.
    *   Installs Python 3.12.1 (if missing).
    *   Installs required Python libraries (`pywinauto`, `pyautogui`, `opencv-python`, `pillow`).
    
*   **Mode 2: Test Execution**
    *   **Get SUT Information**: Dumps Network drivers, BIOS, Build ID, and HP Apps to `SUT_Output.txt`.
    *   **Run Automation: TG4**: Executes the UX test suite.

### 3. Command Line Arguments (Advanced)
You can run the script without user interaction by passing flags to `script_main.bat`:

| Command | Description | 
| :--- | :--- |
| `script_main.bat -InstallPython` | Only run environment setup. |
| `script_main.bat -GetInfo` | Only collect SUT info. |
| `script_main.bat -RunAutomation` | Run the default automation script. |
| `script_main.bat -All` | Run EVERYTHING in sequence (Setup -> Info -> Auto). |

## 🧪 Test Cases & ID Mapping

| Suite | Test ID | Description |
| :--- | :--- | :--- |
| **TG4** | `TC_TG4_001` | Taskbar Alignment & Overlap Check |
| | `TC_TG4_002` | File Explorer Pictures Navigation |
| | `TC_TG4_003` | App Launch via Search Box |
| | `TC_TG4_004` | Global Window Overlap Check |
| **TG_BIO** | `TC_BIO_001` | Windows Hello Setup & Unlock |
| **TG_HK** | `TC_HK_001` | HP Hotkey Software Check |
| | `TC_HK_002` | Fn+Esc System Info Check |
| | `TC_HK_003` | Brightness Control |
| | `TC_HK_004` | LAN/WLAN Switching |
| **TG_APPS** | `TC_APP_001` | HP Bundled Apps Launch Check |
| **TG_FUR** | `TC_FUR_001` | BitLocker/BIOS Update Guide |

---

### TG4: Start Menu, Taskbar & Explorer
*   **Target**: Verifies layout and basic functionality of the Windows Shell.
*   **IDs**: `TC_TG4_001` to `TC_TG4_004`
*   **Steps**:
    1.  Checks Taskbar buttons for visual overlap.
    2.  Opens **File Explorer** and navigates to the **Pictures** folder.
    3.  Launches apps via **Search Box** (Notepad, Calculator).
    4.  Performs a global check for overlapping windows on the desktop.
*   **Usage**: Select Option `2` -> `2` in the menu.

### TG_BIO: Windows Hello & Presence
*   **Target**: Semi-automated validation of Face/Fingerprint login and HP Auto Lock.
*   **Type**: **Interactive / Assisted**.
*   **Steps**:
    1.  Automatically opens **Windows Sign-in Options**.
    2.  Prompts user to enroll Face/Fingerprint manually.
    3.  Automatically **Locks the Workstation** after a countdown.
    4.  User performs unlock test.
    5.  User inputs Pass/Fail result back into the console.
*   **Usage**: Select Option `2` -> `3` in the menu.

### TG_HK: Hotkeys & Hardware Control
*   **Target**: Verify HP-specific hardware controls and software integration.
*   **Steps**:
    1.  **HP Hotkey Support**: Checks if the required software is installed (via Registry/PowerShell).
    2.  **Fn + Esc**: Simulates the key combo by launching `HPSysInfo.exe` and verifying the window appears.
    3.  **Brightness**: Uses WMI to read current brightness, set it to 50%, verify change, then restore.
    4.  **LAN/WLAN Switch**: Monitors network adapter status while prompting the user to plug in an Ethernet cable. (Success = Wi-Fi disconnects automatically).
*   **Usage**: Select Option `2` -> `4` in the menu.

### TG_APPS: HP Apps Launch Check
*   **Target**: Verify bundling and launch capability of key HP Applications.
*   **Scope**: HPSA, myHP, HP Privacy Settings, HP Programmable Key, HP Power Manager, etc.
*   **Steps**: Automatically searches and launches each app, verifies the window title, and closes it. Prompts for manual verification of `myHP` sub-modules.
*   **Usage**: Select Option `2` -> `5` in the menu.

### TG_FUR: BitLocker & BIOS Workflow Guide
*   **Target**: Guided walkthrough for complex BIOS/Security testing.
*   **Type**: **Interactive Guide**.
*   **Scenario**: Turn off BitLocker -> Remove KB -> Downgrade BIOS -> Enable Secure Boot -> Enable BitLocker -> FUR (Firmware Update on Reboot).
*   **Features**:
    *   Displays current BitLocker encryption status (`manage-bde`).
    *   Step-by-step prompts for manual actions (BIOS flashing, rebooting).
    *   Validates expectations for post-reboot state.
*   **Usage**: Select Option `2` -> `6` in the menu.

---

## 🛠️ Utility Tools

### Option 0: Quick System Diagnostic
A lightweight PowerShell utility (`QuickCheck.ps1`) to verify critical system states before testing:
*   **BitLocker**: Shows encryption status, percentage, and key protectors.
*   **Biometrics**: Lists detected IR Cameras and Fingerprint sensors.
*   **Security**: Verifies Secure Boot and TPM readiness.
*   **Usage**: Select Option `2` -> `0` in the menu.

## 📦 Dependencies

*   **OS**: Windows 10 / 11
*   **Language**: PowerShell 5.1+, Python 3.12+
*   **Python Libraries**: `pywinauto`, `pyautogui`, `opencv-python`, `pillow`

---
*Last Updated: 2025-12-18*
