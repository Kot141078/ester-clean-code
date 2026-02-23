import sys
print("=== B6e SMOKE ===")
from telegram.ext import JobQueue
jq = JobQueue()
print("[OK] JobQueue created:", type(jq).__name__)
import apscheduler
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
print("[OK] apscheduler:", getattr(apscheduler,"__version__", "n/a"))
print("SMOKE: OK")