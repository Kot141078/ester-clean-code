import run_ester_fixed as app
import sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

print(f"CHECK 1: SHORT_TERM_MAXLEN = {app.SHORT_TERM_MAXLEN}")
if app.SHORT_TERM_MAXLEN != 500:
    print("❌ FAIL: Memory limit is wrong!")
    sys.exit(1)

print("CHECK 2: Restore function exists...")
if hasattr(app, "restore_context_from_passport"):
    print("✅ PASS: Restore function found.")
else:
    print("❌ FAIL: Restore function missing!")
    sys.exit(1)

print("\n🧪 ALL SYSTEMS GO. ESTER IS READY TO REMEMBER.")