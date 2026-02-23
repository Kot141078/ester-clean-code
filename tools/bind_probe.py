import argparse, socket, sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
p = argparse.ArgumentParser()
p.add_argument("--host", default="127.0.0.1")
p.add_argument("--port", type=int, default=8137)
a = p.parse_args()
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.bind((a.host, a.port))
    print(f"[bind-probe] OK: {(a.host, a.port)}")
finally:
    try: s.close()
    except: pass