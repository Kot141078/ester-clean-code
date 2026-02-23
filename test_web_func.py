import logging
import os
import sys
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def main() -> int:
    root = os.path.dirname(os.path.abspath(__file__))
    if root not in sys.path:
        sys.path.insert(0, root)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

    print("--- 1. Importing Ester Core ---")
    try:
        import run_ester_fixed as app
        print("[OK] Import successful.")
    except ImportError as e:
        print(f"[ERR] Import failed: {e}")
        return 1

    print("\n--- 2. Checking Configuration ---")
    print(f"CLOSED_BOX: {getattr(app, 'CLOSED_BOX', 'Not Found')}")
    print(f"WEB_FACTCHECK: {getattr(app, 'WEB_FACTCHECK', 'Not Found')}")

    print("\n--- 3. EXECUTING get_web_evidence('current bitcoin price') ---")
    print("...waiting for network...")

    try:
        result = app.get_web_evidence("current bitcoin price")
        print("\n--- RESULT ---")
        if result:
            print(f"[OK] DATA RECEIVED ({len(result)} chars):")
            print("-" * 40)
            print(result[:500] + "..." if len(result) > 500 else result)
            print("-" * 40)
        else:
            print("[ERR] RESULT IS EMPTY (Function returned empty string)")
    except Exception as e:
        print(f"[ERR] CRITICAL ERROR during execution: {e}")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
