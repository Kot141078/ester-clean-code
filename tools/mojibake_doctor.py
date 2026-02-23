# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import io
import json
import re
import sys
import tokenize
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence, Tuple


EXIT_OK = 0
EXIT_APPLY_FAILED = 6

_CYR_RE = re.compile(r"[A-Yaa-yaEe]")
_LATIN_MOJIBAKE_RE = re.compile(r"(?:Ð.|Ñ.){2,}")
_RS_PAIR_RE = re.compile(r"(?:[RS][A-Yaa-yaEeҐґЇїІіЄє]){2,}")
_ODD_PAIR_RE = re.compile(r"[RS][ґ№їЅЎўЈђћџ]")
_KNOWN_BAD_TOKENS = ("dney", "Pr")


@dataclass
class FixCandidate:
    start: Tuple[int, int]
    end: Tuple[int, int]
    old: str
    new: str
    token_type: str
    method: str


def _parse_paths(raw: str) -> List[Path]:
    chunks = [x.strip() for x in re.split(r"[;,]", raw or "") if x.strip()]
    out: List[Path] = []
    seen = set()
    for ch in chunks:
        p = Path(ch).resolve()
        key = str(p).lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(p)
    return out


def _count_cyr(text: str) -> int:
    return len(_CYR_RE.findall(text or ""))


def _marker_score(text: str) -> int:
    marks = "ÐÑÃÂ�RS"
    return sum((text or "").count(ch) for ch in marks)


def _printable_text(text: str) -> bool:
    for ch in text:
        if ch in "\n\r\t":
            continue
        if not ch.isprintable():
            return False
    return True


def _looks_utf8_cp1251_mojibake(value: str) -> bool:
    s = value or ""
    if not s:
        return False
    if _LATIN_MOJIBAKE_RE.search(s):
        return True
    if "R" not in s and "S" not in s:
        return False
    if _ODD_PAIR_RE.search(s):
        return True
    if any(tok in s for tok in _KNOWN_BAD_TOKENS):
        return True
    if _RS_PAIR_RE.search(s):
        mark = _marker_score(s)
        rs_count = s.count("R") + s.count("S")
        cyr_count = _count_cyr(s)
        if mark >= 3 and rs_count >= max(2, cyr_count // 4):
            return True
    return False


def _transform_cp1251_utf8(value: str) -> str | None:
    try:
        return value.encode("cp1251", errors="strict").decode("utf-8", errors="strict")
    except Exception:
        return None


def _transform_latin1_utf8(value: str) -> str | None:
    try:
        return value.encode("latin-1", errors="strict").decode("utf-8", errors="strict")
    except Exception:
        return None


def _pick_better(original: str) -> Tuple[str | None, str]:
    if not _looks_utf8_cp1251_mojibake(original):
        return None, ""

    base_cyr = _count_cyr(original)
    base_mark = _marker_score(original)
    best: str | None = None
    best_method = ""
    for method, candidate in (
        ("cp1251->utf8", _transform_cp1251_utf8(original)),
        ("latin1->utf8", _transform_latin1_utf8(original)),
    ):
        if not candidate or candidate == original:
            continue
        if "\ufffd" in candidate:
            continue
        if not _printable_text(candidate):
            continue
        gain_cyr = _count_cyr(candidate) - base_cyr
        gain_marks = base_mark - _marker_score(candidate)
        if gain_cyr <= 0 or gain_marks <= 0:
            continue
        if best is None:
            best = candidate
            best_method = method
            continue
        cur_score = (_count_cyr(best) - base_cyr, base_mark - _marker_score(best))
        nxt_score = (gain_cyr, gain_marks)
        if nxt_score > cur_score:
            best = candidate
            best_method = method
    return best, best_method


def _pos_to_index(text: str, line: int, col: int) -> int:
    lines = text.splitlines(keepends=True)
    line = max(1, line)
    if line > len(lines):
        return len(text)
    return sum(len(lines[i]) for i in range(line - 1)) + min(col, len(lines[line - 1]))


def _collect_candidates(path: Path, text: str) -> List[FixCandidate]:
    candidates: List[FixCandidate] = []
    reader = io.StringIO(text).readline
    for tok in tokenize.generate_tokens(reader):
        if tok.type not in (tokenize.COMMENT, tokenize.STRING):
            continue
        fixed, method = _pick_better(tok.string)
        if not fixed or fixed == tok.string:
            continue
        token_kind = "comment" if tok.type == tokenize.COMMENT else "string"
        candidates.append(
            FixCandidate(
                start=tok.start,
                end=tok.end,
                old=tok.string,
                new=fixed,
                token_type=token_kind,
                method=method,
            )
        )
    return candidates


def _apply_candidates(text: str, candidates: Sequence[FixCandidate]) -> str:
    out = text
    spans: List[Tuple[int, int, str]] = []
    for c in candidates:
        start_idx = _pos_to_index(out, c.start[0], c.start[1])
        end_idx = _pos_to_index(out, c.end[0], c.end[1])
        spans.append((start_idx, end_idx, c.new))
    for start_idx, end_idx, repl in sorted(spans, key=lambda x: x[0], reverse=True):
        out = out[:start_idx] + repl + out[end_idx:]
    return out


def _write_reports(findings: List[Dict[str, Any]], summary: Dict[str, Any], repo_root: Path) -> None:
    jsonl_path = repo_root / "data" / "reports" / "mojibake_report.jsonl"
    md_path = repo_root / "docs" / "mojibake_report.md"
    jsonl_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)

    with jsonl_path.open("w", encoding="utf-8") as f:
        for item in findings:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    lines: List[str] = [
        "# Mojibake Report",
        "",
        f"- mode: {summary['mode']}",
        f"- files_scanned: {summary['files_scanned']}",
        f"- files_changed: {summary['files_changed']}",
        f"- findings: {summary['findings']}",
        "",
        "| path | line | token | method | applied |",
        "|---|---:|---|---|:---:|",
    ]
    for item in findings[:200]:
        lines.append(
            f"| {item['path']} | {item['line']} | {item['token']} | {item['method']} | {str(bool(item['applied'])).lower()} |"
        )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: List[str]) -> int:
    ap = argparse.ArgumentParser(description="Detect/fix mojibake in touched files (offline, stdlib only).")
    ap.add_argument("--scan", action="store_true", help="Report only.")
    ap.add_argument("--apply", action="store_true", help="Apply safe fixes.")
    ap.add_argument("--paths", default="", help="Comma/semicolon separated file paths.")
    args = ap.parse_args(argv)

    mode_apply = bool(args.apply)
    if not args.scan and not args.apply:
        mode_apply = False

    raw_paths = args.paths or ""
    if not raw_paths:
        raw_paths = str(Path.cwd().joinpath(".iter35_touched_files.txt")) if Path(".iter35_touched_files.txt").exists() else ""
    paths = [p for p in _parse_paths(raw_paths) if p.is_file()]

    findings: List[Dict[str, Any]] = []
    files_changed = 0
    apply_failed = False
    for path in paths:
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        candidates = _collect_candidates(path, text)
        if not candidates:
            continue
        changed = False
        if mode_apply:
            try:
                backup = Path(str(path) + ".bak_mojibake")
                if not backup.exists():
                    backup.write_bytes(path.read_bytes())
                new_text = _apply_candidates(text, candidates)
                if new_text != text:
                    path.write_text(new_text, encoding="utf-8")
                    changed = True
                    files_changed += 1
            except Exception:
                apply_failed = True
        for cand in candidates:
            findings.append(
                {
                    "path": str(path.relative_to(Path.cwd())).replace("\\", "/"),
                    "line": int(cand.start[0]),
                    "token": cand.token_type,
                    "method": cand.method,
                    "applied": bool(changed),
                    "before": cand.old[:160],
                    "after": cand.new[:160],
                }
            )

    summary = {
        "ok": not apply_failed,
        "mode": "apply" if mode_apply else "scan",
        "files_scanned": len(paths),
        "files_changed": files_changed,
        "findings": len(findings),
    }
    _write_reports(findings, summary, Path.cwd())
    print(json.dumps(summary, ensure_ascii=False))
    return EXIT_APPLY_FAILED if apply_failed else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
