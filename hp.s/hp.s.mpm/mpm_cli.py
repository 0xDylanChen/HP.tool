import argparse
import sys
import ctypes
import os
from mpm_core import MPMManager, MPMError, AdminRequiredError

def is_admin():
    try:
        return ctypes.windll.shell32.IsUserAnAdmin()
    except:
        return False

def run_as_admin():
    """Relaunches the current script with admin privileges."""
    # Quote arguments to preserve spaces
    params = " ".join([f'"{arg}"' for arg in sys.argv[1:]])
    # sys.executable is the python interpreter
    # sys.argv[0] is this script
    cmd = f'"{sys.argv[0]}"'
    
    try:
        ctypes.windll.shell32.ShellExecuteW(
            None, "runas", sys.executable, f"{cmd} {params}", None, 1
        )
        return True
    except Exception as e:
        print(f"Failed to elevate: {e}")
        return False

def main():
    parser = argparse.ArgumentParser(description="HP MPM Configuration Utility CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommands
    subparsers.add_parser("get-original", help="Get Original BIOS Config")
    subparsers.add_parser("get-unlock", help="Get Config after Unlock")
    subparsers.add_parser("merge", help="Merge Original Config into Unlock Config")
    subparsers.add_parser("set-unlock", help="Apply Unlock Config to BIOS")

    args = parser.parse_args()
    
    # Initialize Manager
    # Assumes the script is running in the directory where BCU is, or relative to it.
    # Current structure: this script is in hp.s/hp.s.mpm/ alongside mpm_core.py
    script_dir = os.path.dirname(os.path.abspath(__file__))
    manager = MPMManager(working_dir=script_dir)

    try:
        if args.command == "get-original":
            print(">>> Getting Original Configuration...")
            output = manager.get_original_config()
            print(output)
            
        elif args.command == "get-unlock":
            print(">>> Getting Unlock Configuration...")
            output = manager.get_unlock_config()
            print(output)
            
        elif args.command == "merge":
            print(">>> Merging Configurations...")
            output = manager.merge_configs()
            print(output)
            
        elif args.command == "set-unlock":
            print(">>> Applying Configuration to BIOS...")
            output = manager.set_unlock_config()
            print(output)
            
    except AdminRequiredError:
        print("!!! Admin privileges required. Attempting to elevate...")
        if not is_admin():
            if run_as_admin():
                print(">>> Elevation requested. Please check the new window.")
            else:
                print("!!! Elevation failed.")
        else:
            print("!!! Already admin but permission denied. Check system state.")
            
    except MPMError as e:
        print(f"!!! Error: {str(e)}")
    except Exception as e:
        print(f"!!! Unexpected Error: {str(e)}")

    # Keep window open if launched via double-click or new window (simple heuristic)
    # If we are in a completely new process that might close immediately.
    # We can check if we are attached to a console? 
    # For now, simplistic input pause if not piped.
    if sys.stdout.isatty():
        input("\nPress Enter to exit...")

if __name__ == "__main__":
    main()
