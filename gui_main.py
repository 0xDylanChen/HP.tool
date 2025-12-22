import customtkinter as ctk
import os
import sys
import re
import threading
import subprocess
import time
from utils import SystemUtils, Diagnostics, MPMUtils, ProjectConfig
from automation_runner import AutomationRunner

# Import version_checker from hp.s
try:
    sys.path.append(str(ProjectConfig.SCRIPTS_DIR))
    import version_checker
except ImportError:
    print("Warning: Could not import version_checker")
    version_checker = None

# Appearance Settings
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

# Constants for Windows Style
FONT_HEADER = ("Segoe UI", 24, "bold")
FONT_SUBHEADER = ("Segoe UI", 18, "bold")
FONT_BODY = ("Segoe UI", 16)
FONT_MONO = ("Consolas", 15)
COLOR_CARD = ("gray85", "gray20")  # Light/Dark mode card colors
COLOR_TRANSPARENT = "transparent"

class ConsoleRedirector:
    def __init__(self, text_widget, tag="stdout"):
        self.text_widget = text_widget
        self.tag = tag

    def write(self, str_val):
        self.text_widget.configure(state="normal")
        self.text_widget.insert("end", str_val, self.tag)
        self.text_widget.see("end")
        self.text_widget.configure(state="disabled")

    def flush(self):
        pass

class HPAutoKitApp(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("HP SUT AutoKit v3.1")
        self.geometry("1280x800")
        self.resizable(True, True)  # Resizable
        
        # Layout: Sidebar (0) + Main Content (1)
        # Layout: Sidebar (0) + Main Content (1)
        # Row 0: Page Container (70%)
        # Row 1: Log Frame (30%)
        self.grid_rowconfigure(0, weight=7)
        self.grid_rowconfigure(1, weight=3)
        self.grid_columnconfigure(1, weight=1)

        self.init_sidebar()
        self.init_pages()
        
        # Select default
        self.select_frame("Home")

    def init_sidebar(self):
        # Windows 11 Style Sidebar: Slightly lighter than background, clean navigation
        self.sidebar = ctk.CTkFrame(self, width=280, corner_radius=0, fg_color=("gray95", "#202020"))
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(7, weight=1) # Spacer

        # App Title area
        title_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        title_frame.grid(row=0, column=0, padx=24, pady=(24, 12), sticky="ew")
        
        # Simple icon representation using text
        ctk.CTkLabel(title_frame, text="⚙️", font=("Segoe UI", 26)).pack(side="left", padx=(0, 10))
        ctk.CTkLabel(title_frame, text="HP AutoKit", font=("Segoe UI Variable Display", 22, "bold")).pack(side="left")
        
        ver_lbl = ctk.CTkLabel(self.sidebar, text="v3.1 Native", font=("Segoe UI", 12), text_color="gray60")
        ver_lbl.grid(row=1, column=0, padx=24, pady=(0, 24), sticky="w")

        # Nav Buttons Container
        self.nav_container = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.nav_container.grid(row=2, column=0, sticky="ew", padx=12)

        self.nav_buttons = {}
        # Unicode icons for buttons
        btns = [
            ("Home", "Home", "🏠"),
            ("System Info", "Info", "ℹ️"),
            ("Diagnostics", "Diag", "🩺"),
            ("Automation", "Auto", "🤖"),
            ("MPM Utility", "MPM", "🔓")
        ]
        
        for i, (text, name, icon) in enumerate(btns):
            # Win11 Nav Button: Transparent by default, corner radius 6
            btn = ctk.CTkButton(self.nav_container, text=f"  {icon}   {text}", anchor="w",
                                height=42, corner_radius=6,
                                font=("Segoe UI Variable Text", 15),
                                fg_color="transparent", text_color=("gray10", "#E0E0E0"),
                                hover_color=("gray85", "#333333"),
                                command=lambda n=name: self.select_frame(n))
            btn.pack(fill="x", pady=2)
            self.nav_buttons[name] = btn
        
        # Bottom area (Help/Settings equivalent)
        help_btn = ctk.CTkButton(self.sidebar, text="  ❓   Help & Docs", anchor="w",
                                 height=42, corner_radius=6,
                                 font=("Segoe UI Variable Text", 14),
                                 fg_color="transparent", text_color=("gray10", "gray70"),
                                 hover_color=("gray85", "#333333"),
                                 command=lambda: self.select_frame("Home"))
        help_btn.grid(row=9, column=0, padx=12, pady=24, sticky="ew")

    def init_pages(self):
        self.frames = {}
        
        # Main content container (Right side)
        self.page_container = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color=COLOR_TRANSPARENT)
        self.page_container.grid(row=0, column=1, sticky="nsew", padx=30, pady=30)
        self.page_container.grid_rowconfigure(0, weight=1)
        self.page_container.grid_columnconfigure(0, weight=1)

        # 1. Home
        self.frames["Home"] = self.create_home_frame(self.page_container)
        # 2. Info
        self.frames["Info"] = self.create_info_frame(self.page_container)
        # 3. Diag
        self.frames["Diag"] = self.create_diag_frame(self.page_container)
        # 4. Auto
        self.frames["Auto"] = self.create_auto_frame(self.page_container)
        # 5. MPM
        self.frames["MPM"] = self.create_mpm_frame(self.page_container)

        # Log Area Container (Row 1)
        log_frame = ctk.CTkFrame(self, fg_color="transparent")
        log_frame.grid(row=1, column=1, sticky="nsew", padx=30, pady=(0, 30))
        log_frame.grid_rowconfigure(1, weight=1)
        log_frame.grid_columnconfigure(0, weight=1)

        # Log Controls (Header)
        log_ctrls = ctk.CTkFrame(log_frame, fg_color="transparent", height=30)
        log_ctrls.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        
        ctk.CTkLabel(log_ctrls, text="Execution Logs", font=("Segoe UI", 14, "bold"), text_color="gray").pack(side="left")
        ctk.CTkButton(log_ctrls, text="Clear Logs", width=100, height=24, font=("Segoe UI", 12), 
                      fg_color="#555", hover_color="#333", command=self.clear_logs).pack(side="right")

        # Tabview
        self.console_view = ctk.CTkTabview(log_frame, height=150, corner_radius=10, fg_color=COLOR_CARD)
        self.console_view.grid(row=1, column=0, sticky="nsew")
        
        # Tabs
        self.console_view.add("Info Log")
        self.console_view.add("System Log")
        
        # Info Log
        self.console_info = ctk.CTkTextbox(self.console_view.tab("Info Log"), font=FONT_MONO, fg_color="transparent")
        self.console_info.pack(fill="both", expand=True, padx=5, pady=5)
        self.console_info.insert("0.0", ">>> Info Log Ready.\n")
        self.console_info.configure(state="disabled")

        # System Log
        self.console_sys = ctk.CTkTextbox(self.console_view.tab("System Log"), font=FONT_MONO, fg_color="transparent")
        self.console_sys.pack(fill="both", expand=True, padx=5, pady=5)
        self.console_sys.insert("0.0", ">>> System Log Ready (Full Details).\n")
        self.console_sys.configure(state="disabled")

    def select_frame(self, name):
        # Hide all pages
        for f in self.frames.values():
            f.grid_forget()
        
        # Update Nav Buttons State (Win11 style)
        for n, btn in self.nav_buttons.items():
            if n == name:
                btn.configure(fg_color=("white", "#3C3C3C"), text_color=("black", "white")) 
            else:
                btn.configure(fg_color="transparent", text_color=("gray10", "#BBBBBB"))

        # Show selected page
        self.frames[name].grid(row=0, column=0, sticky="nsew")

    # --- Page Creators (Windows Settings Style: Header + Cards) ---

    def create_home_frame(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        
        # Header
        ctk.CTkLabel(f, text="Home", font=FONT_HEADER).pack(anchor="w", pady=(0, 20))
        
        # Card: SOP
        card_sop = ctk.CTkFrame(f, fg_color=COLOR_CARD, corner_radius=10)
        card_sop.pack(fill="x", pady=10)
        
        ctk.CTkLabel(card_sop, text="Standard Operating Procedure", font=FONT_SUBHEADER).pack(anchor="w", padx=20, pady=(20, 10))
        
        sop = (
            "1. Check 'System Info' to verify HW configuration.\n"
            "2. Use 'MPM Utility' if BIOS needs unlocking.\n"
            "3. Go to 'Automation' to run test suites.\n"
            "4. Use 'Diagnostics' for quick checks.\n"
        )
        ctk.CTkLabel(card_sop, text=sop, justify="left", font=FONT_BODY, anchor="w").pack(anchor="w", padx=20, pady=(0, 20))
        
        # Card: Status
        card_env = ctk.CTkFrame(f, fg_color=COLOR_CARD, corner_radius=10)
        card_env.pack(fill="x", pady=10)
        
        ctk.CTkLabel(card_env, text="System Status", font=FONT_SUBHEADER).pack(anchor="w", padx=20, pady=(20, 10))
        
        self.env_lbl = ctk.CTkLabel(card_env, text="Checking privileges...", text_color="gray", font=FONT_BODY)
        self.env_lbl.pack(anchor="w", padx=20, pady=(0, 10))
        
        ctk.CTkButton(card_env, text="Install Dependencies", font=FONT_BODY,
                      command=self.run_env_setup, height=35).pack(anchor="w", padx=20, pady=(0, 20))

        if SystemUtils.is_admin():
            self.env_lbl.configure(text="● Running as Administrator", text_color="#4CC14E") # Green
        else:
            self.env_lbl.configure(text="● Not running as Admin", text_color="#FF9800") # Orange

        return f

    def create_info_frame(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(f, text="System Information", font=FONT_HEADER).pack(anchor="w", pady=(0, 20))

        # Controls
        ctrl_frame = ctk.CTkFrame(f, fg_color="transparent")
        ctrl_frame.pack(fill="x", pady=(0, 10))
        
        ctk.CTkButton(ctrl_frame, text="Refresh Info", font=FONT_BODY, command=self.run_get_info).pack(side="left")
        ctk.CTkButton(ctrl_frame, text="Check App Ver", font=FONT_BODY, command=self.run_version_check).pack(side="left", padx=10)
        ctk.CTkButton(ctrl_frame, text="Open Output Folder", font=FONT_BODY,
                      command=lambda: os.startfile(os.path.join(os.getcwd(), "hp.v")) if os.path.exists("hp.v") else os.makedirs("hp.v") or os.startfile("hp.v"),
                      fg_color="gray").pack(side="left", padx=10)

        # Card for Text
        card = ctk.CTkFrame(f, fg_color=COLOR_CARD, corner_radius=10)
        card.pack(fill="both", expand=True)
        
        self.info_text = ctk.CTkTextbox(card, font=FONT_MONO, fg_color="transparent")
        self.info_text.pack(fill="both", expand=True, padx=10, pady=10)
        
        return f

    def create_diag_frame(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(f, text="Diagnostics", font=FONT_HEADER).pack(anchor="w", pady=(0, 20))
        
        # Grid container
        grid = ctk.CTkFrame(f, fg_color="transparent")
        grid.pack(fill="both", expand=True)
        
        checks = [
            ("Drivers", "Check for Yellow Bangs", Diagnostics.check_drivers),
            ("Network", "Ping Connectivity", Diagnostics.check_network_ping),
            ("Battery", "Status & Charge", Diagnostics.check_battery),
            ("BitLocker", "Encryption Status", Diagnostics.check_bitlocker)
        ]

        for i, (title, sub, func) in enumerate(checks):
            # Card for each diag
            card = ctk.CTkFrame(grid, fg_color=COLOR_CARD, corner_radius=10)
            card.grid(row=i // 2, column=i % 2, padx=10, pady=10, sticky="nsew")
            
            ctk.CTkLabel(card, text=title, font=FONT_SUBHEADER).pack(anchor="w", padx=20, pady=(15, 0))
            ctk.CTkLabel(card, text=sub, font=("Segoe UI", 12), text_color="gray").pack(anchor="w", padx=20, pady=(0, 10))
            
            ctk.CTkButton(card, text="Run Check", font=FONT_BODY, height=35,
                          command=lambda fn=func, nm=title: self.run_diag(nm, fn)).pack(anchor="w", padx=20, pady=(0, 15))
        
        grid.grid_columnconfigure(0, weight=1)
        grid.grid_columnconfigure(1, weight=1)
        grid.grid_rowconfigure(0, weight=1)
        grid.grid_rowconfigure(1, weight=1)
        return f

    def create_auto_frame(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(f, text="Automation Suite", font=FONT_HEADER).pack(anchor="w", pady=(0, 20))
        
        # Test Selection Area
        sel_frame = ctk.CTkFrame(f, fg_color=COLOR_CARD, corner_radius=10)
        sel_frame.pack(fill="x", pady=10)
        
        ctk.CTkLabel(sel_frame, text="Select Test Scenarios:", font=FONT_SUBHEADER).pack(anchor="w", padx=20, pady=(15, 10))
        
        # Checkboxes
        self.chk_vars = {}
        self.scenarios = ["KB", "TG1", "TG2", "TG3", "TG4"]
        
        chk_container = ctk.CTkFrame(sel_frame, fg_color="transparent")
        chk_container.pack(fill="x", padx=20, pady=(0, 15))
        
        for sc in self.scenarios:
            var = ctk.StringVar(value="on" if sc == "TG4" else "off") # Default TG4 on
            self.chk_vars[sc] = var
            ctk.CTkCheckBox(chk_container, text=sc, variable=var, onvalue="on", offvalue="off", font=FONT_BODY).pack(side="left", padx=10)

        # Controls
        ctrl = ctk.CTkFrame(f, fg_color="transparent")
        ctrl.pack(fill="x", pady=(0, 10))
        
        ctk.CTkButton(ctrl, text="Scan Coverage", font=FONT_BODY, command=self.run_auto_scan).pack(side="left", padx=5)
        ctk.CTkButton(ctrl, text="Run Automated Tests", font=FONT_BODY, fg_color="#4CC14E", hover_color="#3DA03E", 
                      command=self.run_auto_exec).pack(side="left", padx=5)
        
        # Note: Output is now redirected to the Main Log area as requested.
        ctk.CTkLabel(f, text="ℹ️ Results will be displayed in the Log panel below.", text_color="gray", font=("Segoe UI", 12)).pack(anchor="w", padx=5, pady=5)

        return f

    def get_selected_testfiles(self):
        selected_files = []
        base_dir = os.path.join(os.getcwd(), "testcase")
        
        for sc in self.scenarios:
            if self.chk_vars[sc].get() == "on":
                # specific mapping logic
                filename = f"testcase {sc}.txt"
                path = os.path.join(base_dir, filename)
                selected_files.append(path)
        
        return selected_files

    def run_auto_scan(self):
        files = self.get_selected_testfiles()
        if not files:
            self.log("No test scenarios selected.", level="info")
            return

        def task():
            self.log(f"Scanning {len(files)} files for automation...", level="info")
            runner = AutomationRunner(files)
            data = runner.scan_coverage()
            
            if isinstance(data, str):
                self.log(f"Error: {data}", level="info")
            else:
                msg = f"COVERAGE ANALYSIS ({', '.join([os.path.basename(f) for f in files])}):\n"
                msg += f"Total: {data['total']} | Auto: {data['auto']} | Cov: {data['coverage']:.1f}%\n"
                msg += "Automated Items:\n"
                for item in data['items']:
                    if item['status'] == 'Auto':
                        msg += f" [{item['file']}] L{item['line_no']}: {item['feature']}\n"
                
                self.log(msg, level="info")
        self.run_thread(task)

    def run_auto_exec(self):
        files = self.get_selected_testfiles()
        if not files:
            self.log("No test scenarios selected.", level="info")
            return

        def task():
            self.log(f"Executing automation for {len(files)} files...", level="info")
            runner = AutomationRunner(files)
            
            report = runner.run_automation()
            self.log(report, level="info")
            self.log("Automation Complete.", level="info")

        self.run_thread(task)

    def create_mpm_frame(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(f, text="MPM Utility", font=FONT_HEADER).pack(anchor="w", pady=(0, 20))
        
        card = ctk.CTkFrame(f, fg_color=COLOR_CARD, corner_radius=10)
        card.pack(fill="x", pady=10)
        
        btns = [
            ("1. Get Original Config", "GET_ORIG"),
            ("2. Get Unlock Config", "GET_UNLOCK"),
            ("3. Merge Configs", "MERGE"),
            ("4. Set Unlock Config", "SET_UNLOCK")
        ]
        
        for name, script in btns:
            row = ctk.CTkFrame(card, fg_color="transparent")
            row.pack(fill="x", padx=10, pady=5)
            
            ctk.CTkLabel(row, text=name, font=FONT_BODY, width=250, anchor="w").pack(side="left", padx=10)
            ctk.CTkButton(row, text="Run", width=100, font=FONT_BODY, height=30,
                          command=lambda s=script: self.run_mpm_script(s)).pack(side="right", padx=10)
        
        # Spacer for padding at bottom of card
        ctk.CTkFrame(card, height=10, fg_color="transparent").pack()
        
        return f

    # --- Actions ---

    def log(self, msg, level="info"):
        """
        Logs a message to the GUI and text files.
        level="info": Writes to Info Log (GUI+File) AND System Log (GUI+File).
        level="system": Writes ONLY to System Log (GUI+File).
        """
        timestamp = time.strftime('%H:%M:%S')
        full_msg = f"[{timestamp}] {msg}"
        
        # Ensure logs dir exists (redundant check but safe)
        if not os.path.exists("logs"):
            os.makedirs("logs")

        # Helper to write to file
        def write_file(name, text):
            try:
                with open(os.path.join("logs", name), "a", encoding="utf-8") as f:
                    f.write(text + "\n")
            except:
                pass # Ignore logging errors to prevent crash

        # 1. System Log (Always receives everything)
        self.console_sys.configure(state="normal")
        self.console_sys.insert("end", full_msg + "\n")
        self.console_sys.see("end")
        self.console_sys.configure(state="disabled")
        write_file("system_log.txt", full_msg)

        # 2. Info Log (Only for high-level info)
        if level == "info":
            self.console_info.configure(state="normal")
            self.console_info.insert("end", full_msg + "\n")
            self.console_info.see("end")
            self.console_info.configure(state="disabled")
            write_file("info_log.txt", full_msg)

    def clear_logs(self):
        """Clears GUI logs and truncates log files."""
        # GUI
        self.console_info.configure(state="normal")
        self.console_info.delete("0.0", "end")
        self.console_info.configure(state="disabled")
        
        self.console_sys.configure(state="normal")
        self.console_sys.delete("0.0", "end")
        self.console_sys.configure(state="disabled")
        
        # Files
        if os.path.exists("logs"):
            for f in ["info_log.txt", "system_log.txt"]:
                try:
                    open(os.path.join("logs", f), 'w').close()
                except: pass
        
        self.log("Logs cleared.", level="info")

    def run_env_setup(self):
        def task():
            self.log("Starting Environment Setup (pip install)...", level="system")
            res = SystemUtils.setup_environment()
            self.log(res)
            if "ready" in res:
                self.env_lbl.configure(text="● Environment Setup Complete", text_color="#4CC14E")
        self.run_thread(task)

    def run_thread(self, target):
        threading.Thread(target=target, daemon=True).start()

    def run_get_info(self):
        def task():
            self.log("Gathering SUT Info... (This may take 10-20s)", level="system")
            info = SystemUtils.get_sut_info()
            
            # Update UI
            text = ""
            for k, v in info.items():
                if isinstance(v, list):
                    text += f"{k}:\n"
                    for item in v:
                        text += f"  - {item}\n"
                else:
                    text += f"{k}: {v}\n"
            
            self.info_text.delete("0.0", "end")
            self.info_text.insert("0.0", text)
            
            # Save
            path = os.path.join("hp.v", "SUT_Output.csv")
            if not os.path.exists("hp.v"): os.makedirs("hp.v")
            SystemUtils.save_sut_info(info, path)
            self.log(f"Info saved to {path}")
            
        self.run_thread(task)

    def run_version_check(self):
        def task():
            self.log("Running HP App Version Check...", level="system")
            
            if version_checker:
                try:
                    # Run the checker directly
                    version_checker.main(project_root=ProjectConfig.ROOT)
                    
                    # Find latest generated report in hp.v
                    output_dir = ProjectConfig.OUTPUT_DIR
                    found = False
                    
                    if output_dir.exists():
                        files = list(output_dir.glob("*.txt"))
                        if files:
                            # Sort by modification time
                            latest_file = max(files, key=os.path.getmtime)
                            content = latest_file.read_text(encoding='utf-8')
                            
                            def update_ui():
                                self.info_text.delete("0.0", "end")
                                self.info_text.insert("0.0", content)
                            self.after(0, update_ui)
                            self.log(f"Report loaded from {latest_file.name}", level="info")
                            found = True
                    
                    if not found:
                        self.log("Version Check Finished. No report found in hp.v.", level="info")

                except Exception as e:
                    self.log(f"Error executing version_checker: {e}", level="info")
            else:
                self.log("Error: version_checker module not loaded (import failed).", level="info")

        self.run_thread(task)

    def run_diag(self, name, func):
        def task():
            self.log(f"Running {name}...", level="system")
            res = func()
            self.log(f"Result:\n{res}")
        self.run_thread(task)



    def run_mpm_script(self, action_key):
        def task():
            self.log(f"Executing MPM Action: {action_key}...", level="system")
            
            mapping = {
                "GET_ORIG": MPMUtils.get_original_config,
                "GET_UNLOCK": MPMUtils.get_unlock_config,
                "MERGE": MPMUtils.merge_configs,
                "SET_UNLOCK": MPMUtils.set_unlock_config
            }
            
            func = mapping.get(action_key)
            if func:
                res = func()
                self.log(f"Result:\n{res}")
            else:
                self.log(f"Error: Unknown action {action_key}")

        self.run_thread(task)

    def on_close(self):
        self.destroy()

if __name__ == "__main__":
    if not SystemUtils.is_admin():
        SystemUtils.elevate()
    
    app = HPAutoKitApp()
    app.mainloop()