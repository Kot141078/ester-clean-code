# -*- coding: utf-8 -*-
# Simple log scanner producing TSV/JSON reports.
# Patterns targeted:
# - ERROR / WARNING lines
# - Environment mutations ($env:KEY=... and Set-Item -Path env:...)
# - HTTP requests ("GET /", "POST /", "Running on http://", etc.)
# - Tail (last 200 lines)

import argparse, os, re, json, collections
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def read_text_lossy(path: str) -> str:
    with open(path, 'rb') as f:
        raw = f.read()
    for enc in ('utf-8', 'cp1251', 'latin-1'):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode('utf-8', 'ignore')

def ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

def write_text(path: str, text: str) -> None:
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(text)

def write_tsv(path: str, rows):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        for row in rows:
            f.write("\t".join(str(x) for x in row) + "\n")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    txt = read_text_lossy(args.log)
    lines = txt.splitlines()
    ensure_dir(args.out)

    errors = []
    warnings = []
    env_sets = []
    http = []

    re_err = re.compile(r'(^|\b)(ERROR|Error|Traceback\b)', re.IGNORECASE)
    re_warn = re.compile(r'(^|\b)(WARNING|Warn|UserWarning|DeprecationWarning)', re.IGNORECASE)
    re_env1 = re.compile(r'^\s*\$env:([A-Za-z_][A-Za-z0-9_]*)\s*=\s*["\']?(.+?)["\']?\s*$')
    re_env2 = re.compile(r'^\s*Set-Item\s+-Path\s+env:([A-Za-z_][A-Za-z0-9_]*)\s+-Value\s+["\']?(.+?)["\']?\s*$',
                         re.IGNORECASE)
    re_http = re.compile(r'("GET\s+/[^"]*"|"POST\s+/[^"]*"|Running on http://\S+|http://127\.0\.0\.1:\d+|/favicon\.ico)')

    for i, line in enumerate(lines, start=1):
        if re_err.search(line):
            errors.append((i, line.strip()))
        if re_warn.search(line):
            warnings.append((i, line.strip()))
        m1 = re_env1.match(line)
        if m1:
            env_sets.append((i, m1.group(1), m1.group(2)))
        m2 = re_env2.match(line)
        if m2:
            env_sets.append((i, m2.group(1), m2.group(2)))
        if re_http.search(line):
            http.append((i, line.strip()))

    def top_counts(items, n=20):
        counter = collections.Counter([t[1] for t in items])
        return counter.most_common(n)

    top_errors = top_counts(errors)
    top_warnings = top_counts(warnings)

    tail_200 = "\n".join(lines[-200:]) if len(lines) > 200 else "\n".join(lines)

    write_tsv(os.path.join(args.out, "errors.tsv"), errors)
    write_tsv(os.path.join(args.out, "warnings.tsv"), warnings)
    write_tsv(os.path.join(args.out, "env_sets.tsv"), env_sets)
    write_tsv(os.path.join(args.out, "http_requests.tsv"), http)
    write_text(os.path.join(args.out, "tail_200.txt"), tail_200)

    report = {
        "input": os.path.abspath(args.log),
        "out_dir": os.path.abspath(args.out),
        "counts": {
            "lines": len(lines),
            "errors": len(errors),
            "warnings": len(warnings),
            "env_sets": len(env_sets),
            "http_requests": len(http),
        },
        "top_errors": top_errors,
        "top_warnings": top_warnings,
        "artifacts": [
            "errors.tsv",
            "warnings.tsv",
            "env_sets.tsv",
            "http_requests.tsv",
            "tail_200.txt"
        ]
    }
    write_text(os.path.join(args.out, "log_report.json"), json.dumps(report, ensure_ascii=False, indent=2))

    print("OK: reports written")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())