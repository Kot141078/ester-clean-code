# tools/strip_utf8_bom.py
import os
import sys
import time
import shutil
import tempfile
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def strip_bom_inplace(path: str) -> int:
    """
    Removes UTF-8 BOM (EF BB BF) from the start of file, in-place via temp + atomic replace.
    Returns:
      0 - nothing changed (no BOM)
      1 - BOM removed
    """
    path = os.path.abspath(path)
    if not os.path.isfile(path):
        raise FileNotFoundError(path)

    # Read only first 3 bytes
    with open(path, "rb") as src:
        head = src.read(3)

    bom = b"\xef\xbb\xbf"
    if head != bom:
        return 0

    # Backup
    ts = time.strftime("%Y%m%d_%H%M%S")
    bak = f"{path}.bak_bomfix_{ts}"
    shutil.copy2(path, bak)

    # Write to temp in same directory, then atomic replace
    d = os.path.dirname(path)
    fd, tmp = tempfile.mkstemp(prefix=os.path.basename(path) + ".tmp_", dir=d)
    try:
        with os.fdopen(fd, "wb") as out, open(path, "rb") as src:
            # Skip BOM
            src.seek(3)
            shutil.copyfileobj(src, out, length=1024 * 1024)
            out.flush()
            os.fsync(out.fileno())

        os.replace(tmp, path)
    except Exception:
        # Best-effort cleanup
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass
        raise

    return 1


def main(argv: list[str]) -> int:
    p = argv[1] if len(argv) > 1 else r".\data\memory\memory.json"
    changed = strip_bom_inplace(p)
    if changed:
        print(f"[OK] BOM removed: {os.path.abspath(p)}")
    else:
        print(f"[OK] No BOM: {os.path.abspath(p)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))