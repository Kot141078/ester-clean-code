from __future__ import annotations

import argparse
from pathlib import Path


def normalize_bytes(data: bytes) -> bytes:
    # Normalize mixed/legacy endings into LF-only text.
    normalized = data.replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    if not normalized.endswith(b"\n"):
        normalized += b"\n"
    return normalized


def normalize_file(path: Path) -> bool:
    original = path.read_bytes()
    normalized = normalize_bytes(original)
    if normalized != original:
        path.write_bytes(normalized)
        return True
    return False


def iter_targets(patterns: list[str]) -> list[Path]:
    targets: list[Path] = []
    seen: set[Path] = set()
    for pattern in patterns:
        for path in sorted(Path(".").glob(pattern)):
            if path.is_file():
                resolved = path.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    targets.append(path)
    return targets


def main() -> int:
    parser = argparse.ArgumentParser(description="Normalize file EOL to LF.")
    parser.add_argument("patterns", nargs="+", help="Glob patterns to normalize")
    args = parser.parse_args()

    changed = 0
    for file_path in iter_targets(args.patterns):
        if normalize_file(file_path):
            changed += 1
            print(f"UPDATED {file_path.as_posix()}")

    print(f"DONE changed={changed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
