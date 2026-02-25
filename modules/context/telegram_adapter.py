from modules.memory.facade import memory_add, ESTER_MEM_FACADE
# DISABLED DUPLICATE ADAPTER
# This file has been disabled to avoid a 409 conflict with the underlying adapter.
def listen():
    print("YuTG-Dummosch This adapter is disabled. The main one works in modules/telegram_adapter.po")
def start_background():
    listen()
    return {
        "ok": True,
        "started": False,
        "reason_code": "duplicate_adapter_disabled",
        "how_to_enable": "Use the primary adapter in modules/telegram_adapter.py only.",
    }
if __name__ == "__main__":
    print(start_background())
