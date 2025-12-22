from automation_runner import AutomationRunner
import json

runner = AutomationRunner('testcase.txt')
data = runner.scan_coverage()

print(f"TOTAL_ITEMS:{data['total']}")
print(f"AUTO_ITEMS:{data['auto']}")
print(f"COVERAGE:{data['coverage']}")

print("--- AUTOMATED ITEMS ---")
for item in data['items']:
    if item['status'] == 'Auto':
        print(f"LINE:{item['line_no']}|FEATURE:{item['feature']}|CONTENT:{item['content'][:50]}")
