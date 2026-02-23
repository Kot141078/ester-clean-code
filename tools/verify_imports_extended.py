from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# -*- coding: utf-8 -*-
def _try(name, fn):
    try:
        fn()
        print(f"[OK] {name}")
    except Exception as e:
        print(f"[ERR] {name}: {e}")

def main():
    tests = [
        ("modules.usb.scanner", lambda: __import__("modules.usb", fromlist=["scanner"]).scanner),
        ("modules.lan.sync", lambda: __import__("modules.lan", fromlist=["sync"]).sync),
        ("modules.lmstudio.detect", lambda: __import__("modules.lmstudio", fromlist=["detect"]).detect()),
        ("modules.storage.FileStore", lambda: __import__("modules.storage", fromlist=["FileStore"]).FileStore),
        ("modules.transport.send", lambda: __import__("modules.transport", fromlist=["send"]).send("t", b"x")),
        ("modules.compliance.gdpr_check", lambda: __import__("modules.compliance", fromlist=["gdpr_check"]).gdpr_check({})),
        ("modules.acceptance.smoke", lambda: __import__("modules.acceptance", fromlist=["smoke"]).smoke()),
        ("modules.env.get_bool", lambda: __import__("modules.env", fromlist=["get_bool"]).get_bool("X", False)),
        ("modules.jobs.enqueue", lambda: __import__("modules.jobs", fromlist=["enqueue"]).enqueue("k", {})),
        ("modules.judge.select_best", lambda: __import__("modules.judge", fromlist=["select_best"]).select_best(["a","bbb"])),
    ]
    for name, fn in tests:
        _try(name, fn)

if __name__ == "__main__":
    main()