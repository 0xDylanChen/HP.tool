# HP SUT AutoKit v3.1

HP SUT AutoKit is an integrated automation toolkit designed for HP SUT (System Under Test) environment setup, hardware information collection, system diagnostics, and BIOS configuration management. It provides both a Graphical User Interface (GUI) and a Command Line Interface (CLI) to improve efficiency.

## 🚀 Key Features

*   **System Information (System Info)**: Automatically scans and aggregates CPU, Memory, BIOS version, Build ID, GPU, and Network driver info. Exports to CSV reports.
*   **MPM & BIOS Config (MPM Utility)**: Integrates HP BiosConfigUtility (BCU) for extracting, merging, and applying BIOS configuration files with logic for MAC/Serial field protection.
*   **Diagnostics**: Quick checks for driver errors (Yellow Bangs), network connectivity, battery status, and BitLocker encryption.
*   **Automation Suite**: Integrated test scenarios (TG4, TG_BIO, TG_HK, etc.) with background execution and logging.

## 📂 Project Structure

```text
C:\HP_Script\
├── gui_main.py          # Main GUI Entry (CustomTkinter)
├── utils.py             # System utilities and common logic
├── requirements.txt     # Python dependencies
├── hp.s/                # Scripts and core logic
│   ├── main_controller.ps1   # PowerShell Controller (CLI Entry)
│   ├── automation_runner.py  # Automation engine
│   ├── version_checker.py    # Software version comparison tool
│   └── hp.s.mpm/             # BIOS Config Module (MPM)
│       ├── mpm_core.py       # Enterprise core logic
│       ├── mpm_cli.py        # Unified CLI tool
│       └── BiosConfigUtility64.exe  # HP BCU component
└── hp.v/                # Output directory (Reports and CSVs)
```

## 🛠️ Setup and Requirements

1.  **Admin Privileges**: This tool requires **Administrator** rights for hardware access.
2.  **Python**: Python 3.10+ is recommended.
3.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
    *Alternatively, use "Install Dependencies" in gui_main.py.*

## 📖 Usage

### Graphical Interface (Recommended)
Run the main application:
```bash
python gui_main.py
```
Use the sidebar to navigate between modules.

### Command Line Interface (MPM Only)
To use MPM functions via script:
```bash
cd hp.s/hp.s.mpm/
python mpm_cli.py get-original   # Get original BIOS config
python mpm_cli.py merge          # Merge critical fields
python mpm_cli.py set-unlock     # Apply config to BIOS
```

## 🏗️ Technical Details: MPM Module
The MPM module uses a **Logic-UI Separation** principle:
*   **`mpm_core.py`**: Encapsulates all BCU commands and data merge algorithms.
*   **`mpm_cli.py`**: Handles user input, argument parsing, and UAC elevation.
*   **Merge Rules**:
    *   Preserves `Serial Number`, `Product Name`, and `Feature Byte`.
    *   Restores `MAC Address` from backup if the template value is all-zero.

## 📝 Maintenance
*   To modify automation tests, edit `hp.s/automation_runner.py`.
*   To add BIOS fields for merging, modify `FIELDS_TO_COPY` in `hp.s/hp.s.mpm/mpm_core.py`.

---
*© 2025 HP SUT Automation Framework*
