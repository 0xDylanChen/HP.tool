
import os

new_code = """    def create_auto_frame(self, parent):
        f = ctk.CTkFrame(parent, fg_color="transparent")
        ctk.CTkLabel(f, text="Automation Suite", font=FONT_HEADER).pack(anchor="w", pady=(0, 20))
        
        # Controls
        ctrl = ctk.CTkFrame(f, fg_color="transparent")
        ctrl.pack(fill="x", pady=(0, 10))
        
        ctk.CTkButton(ctrl, text="Scan Coverage", font=FONT_BODY, command=self.run_auto_scan).pack(side="left", padx=5)
        ctk.CTkButton(ctrl, text="Run Automated Tests", font=FONT_BODY, fg_color="#4CC14E", hover_color="#3DA03E", 
                      command=self.run_auto_exec).pack(side="left", padx=5)

        # Output Area
        self.auto_out = ctk.CTkTextbox(f, font=FONT_MONO, fg_color=COLOR_CARD)
        self.auto_out.pack(fill="both", expand=True, pady=10)
        self.auto_out.insert("0.0", ">>> Ready. Click 'Scan Coverage' to analyze testcase.txt.\\n")
        self.auto_out.configure(state="disabled")

        return f
"""

with open("gui_main.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

start_idx = -1
end_idx = -1

for i, line in enumerate(lines):
    if "def create_auto_frame(self, parent):" in line:
        start_idx = i
    if "return f" in line and start_idx != -1 and i > start_idx:
        end_idx = i
        break

if start_idx != -1 and end_idx != -1:
    print(f"Found block: {start_idx} to {end_idx}")
    # Replace
    final_lines = lines[:start_idx] + [new_code] + lines[end_idx+1:]
    with open("gui_main.py", "w", encoding="utf-8") as f:
        f.writelines(final_lines)
    print("Patched successfully.")
else:
    print("Could not find block.")
