# -*- coding: utf-8 -*-
"""tools/clean_markers.py

Safe marker cleaner:
- Scans .py files.
- Comments out explicit marker lines (e.g. c=a+b) when they are not already comments.
- Leaves other code untouched.
"""
from __future__ import annotations

import logging
import os
from typing import Dict, List

logging.basicConfig(
    filename='ester_clean.log',
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
)
logger = logging.getLogger('ester_clean')

MARKERS = ('c=a+b',)
SKIP_DIRS = {'.git', '.venv', '__pycache__'}


def _should_skip_dir(path: str) -> bool:
    parts = {p.lower() for p in path.split(os.sep)}
    return any(x in parts for x in SKIP_DIRS)


def clean_project(root_dir: str = '.') -> Dict[str, object]:
    fixed: List[str] = []
    for folder, _, files in os.walk(root_dir):
        if _should_skip_dir(folder):
            continue
        for file in files:
            if not file.endswith('.py'):
                continue
            path = os.path.join(folder, file)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    lines = f.read().splitlines()
            except Exception:
                continue

            changed = False
            for i, line in enumerate(lines):
                stripped = line.strip()
                if stripped.startswith('#'):
                    continue
                if any(marker in stripped for marker in MARKERS):
                    lines[i] = f'# {line}' if line else '#'
                    changed = True

            if not changed:
                continue

            with open(path, 'w', encoding='utf-8') as f:
                f.write('\n'.join(lines) + '\n')
            fixed.append(path)
            logger.info('Cleaned marker(s): %s', path)

    return {'ok': True, 'fixed': fixed}


if __name__ == '__main__':
    result = clean_project()
    print(result)
