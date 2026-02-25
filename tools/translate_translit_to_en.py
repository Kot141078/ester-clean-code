#!/usr/bin/env python3
"""Bulk-translate transliterated Russian comments/UI strings to English.

Conservative mode:
- translates comments in Python and common text/code files;
- translates quoted UI/service phrases in JS/HTML/CSS/MD and optionally Python strings;
- skips binary/build/vendor folders.

Requires `googletrans` (already available in this environment).
"""

from __future__ import annotations

import argparse
import ast
import asyncio
import io
import re
import tokenize
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from googletrans import Translator


DEFAULT_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".html",
    ".htm",
    ".css",
    ".md",
    ".txt",
    ".yaml",
    ".yml",
    ".ps1",
    ".sh",
    ".env",
    ".service",
    ".conf",
}

DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "artifacts",
    "__pycache__",
    "models--sentence-transformers--all-MiniLM-L6-v2",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".idea",
    ".vscode",
}

HASH_COMMENT_EXTS = {
    ".sh",
    ".ps1",
    ".yaml",
    ".yml",
    ".env",
    ".service",
    ".conf",
    ".txt",
    ".md",
    ".py",
}

SLASH_COMMENT_EXTS = {
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".css",
    ".html",
    ".htm",
}

QUOTED_STRING_EXTS = {
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".html",
    ".htm",
    ".css",
    ".md",
}

HTML_EXTS = {".html", ".htm"}


ENGLISH_STOPWORDS = {
    "the",
    "and",
    "for",
    "with",
    "this",
    "that",
    "from",
    "you",
    "your",
    "are",
    "is",
    "was",
    "were",
    "to",
    "in",
    "on",
    "of",
    "as",
    "or",
    "if",
    "not",
    "can",
    "will",
    "by",
    "be",
    "at",
    "it",
    "we",
    "our",
}

TRANSLIT_ROOTS = (
    "chto",
    "kak",
    "esli",
    "eto",
    "dlya",
    "nuzh",
    "mozh",
    "dolzh",
    "vniman",
    "oshib",
    "rabot",
    "zapusk",
    "prover",
    "udal",
    "sohran",
    "peren",
    "vrem",
    "sdel",
    "popyt",
    "podkly",
    "otkly",
    "razdel",
    "bukv",
    "komand",
    "tolko",
    "nikogda",
    "otchet",
    "shablon",
    "razmer",
    "aktivn",
    "sozdann",
    "posledn",
    "sobyti",
    "uspekh",
    "uspesh",
    "zhurnal",
    "svitk",
    "poka",
    "roy",
    "agent",
    "yavn",
    "skryt",
    "soby",
    "soob",
    "zapis",
    "obnov",
    "vykhod",
    "vkhod",
    "sled",
    "obrabot",
    "klyuch",
    "zapros",
    "otvet",
    "prosto",
    "udob",
    "rasshir",
    "otdel",
    "svodk",
    "khronolog",
    "pust",
    "deystv",
    "perezagruz",
    "nastro",
    "podskaz",
)

TRANSLIT_CHUNK_RE = re.compile(r"\b[a-z]{2,}\b")
Cyrillic_RE = re.compile(r"[а-яА-ЯёЁ]")
PH_RE = re.compile(r"(\{[^{}]*\}|\$\{[^{}]*\}|%[0-9.]*[a-zA-Z])")
DOUBLE_QUOTE_RE = re.compile(r'"((?:\\.|[^"\\])*)"')
SINGLE_QUOTE_RE = re.compile(r"'((?:\\.|[^'\\])*)'")
HTML_TEXT_RE = re.compile(r">([^<>\n]+)<")
FORCE_TRANSLIT_RE = re.compile(
    r"\b("
    r"esli|dlya|kak|chto|eto|nuzh|mozh|dolzh|skrytyy|yavnyy|"
    r"zapus|proverk|oshibk|sobyti|zadach|otchet|shablon|poka|"
    r"tolko|zhurnal|svitk|zapros|otvet|podkly|otkly|"
    r"sohran|udal|vniman|deystv|klyuch|prosto|rasshir|obnov"
    r")\w*\b",
    flags=re.IGNORECASE,
)


@dataclass
class Replacement:
    file_path: Path
    start: int
    end: int
    source_text: str
    encode_mode: str = "plain"
    quote_char: str = '"'


def should_translate_text(raw: str) -> bool:
    text = (raw or "").strip()
    if len(text) < 3:
        return False
    if Cyrillic_RE.search(text):
        return False

    words = TRANSLIT_CHUNK_RE.findall(text.lower())
    if len(words) < 2:
        return False
    if FORCE_TRANSLIT_RE.search(text):
        return True

    translit_hits = 0
    phonetic_hits = 0
    english_hits = 0
    for w in words:
        if w in ENGLISH_STOPWORDS:
            english_hits += 1
        if any(w.startswith(root) for root in TRANSLIT_ROOTS):
            translit_hits += 1
        if any(ch in w for ch in ("kh", "zh", "ch", "sh", "ts", "ya", "yu", "yo")):
            phonetic_hits += 1

    score = translit_hits + phonetic_hits
    if translit_hits >= 2 and english_hits < len(words):
        return True
    if translit_hits >= 1 and score >= 2 and english_hits <= (len(words) // 2):
        return True
    if phonetic_hits >= 3 and english_hits == 0:
        return True
    if score < 2:
        return False
    if score <= english_hits:
        return False

    return True


def line_starts(text: str) -> List[int]:
    starts = [0]
    for i, ch in enumerate(text):
        if ch == "\n":
            starts.append(i + 1)
    return starts


def pos_to_offset(starts: List[int], pos: Tuple[int, int]) -> int:
    line, col = pos
    return starts[line - 1] + col


def discover_files(root: Path, exts: set[str], exclude_dirs: set[str]) -> List[Path]:
    out: List[Path] = []
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        if p.suffix.lower() not in exts:
            continue
        parts = {part.lower() for part in p.parts}
        if any(ed.lower() in parts for ed in exclude_dirs):
            continue
        out.append(p)
    return out


def decode_quoted_body(body: str) -> str:
    # Safe, minimal unescape for translation quality.
    return (
        body.replace("\\n", "\n")
        .replace("\\t", "\t")
        .replace("\\r", "\r")
        .replace('\\"', '"')
        .replace("\\'", "'")
    )


def encode_quoted_body(text: str, quote_char: str) -> str:
    escaped = text.replace("\\", "\\\\")
    escaped = escaped.replace("\n", "\\n").replace("\t", "\\t").replace("\r", "\\r")
    escaped = escaped.replace(quote_char, "\\" + quote_char)
    return escaped


def find_comment_start(line: str, marker: str) -> int:
    in_single = False
    in_double = False
    esc = False
    i = 0
    while i < len(line):
        ch = line[i]
        if esc:
            esc = False
            i += 1
            continue
        if ch == "\\":
            esc = True
            i += 1
            continue
        if ch == "'" and not in_double:
            in_single = not in_single
            i += 1
            continue
        if ch == '"' and not in_single:
            in_double = not in_double
            i += 1
            continue
        if not in_single and not in_double:
            if marker == "#" and ch == "#":
                return i
            if marker == "//" and ch == "/" and i + 1 < len(line) and line[i + 1] == "/":
                # Avoid URL protocol fragments.
                if i > 0 and line[i - 1] == ":":
                    i += 2
                    continue
                return i
        i += 1
    return -1


def collect_python_replacements(path: Path, text: str, include_strings: bool) -> List[Replacement]:
    starts = line_starts(text)
    replacements: List[Replacement] = []

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except Exception:
        return replacements

    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            s = tok.string
            if s.startswith("#!"):
                continue
            payload = s[1:]
            stripped = payload.lstrip()
            if not stripped or not should_translate_text(stripped):
                continue
            lead_len = len(payload) - len(stripped)
            st = pos_to_offset(starts, tok.start) + 1 + lead_len
            en = st + len(stripped)
            replacements.append(
                Replacement(
                    file_path=path,
                    start=st,
                    end=en,
                    source_text=stripped,
                    encode_mode="plain",
                )
            )
            continue

        if not include_strings or tok.type != tokenize.STRING:
            continue

        lit = tok.string
        m = re.match(r"(?is)^([rubf]*)('''|\"\"\"|'|\")", lit)
        if not m:
            continue
        prefix = (m.group(1) or "").lower()
        quote = m.group(2)
        qlen = len(quote)
        if "b" in prefix or "r" in prefix:
            continue
        inner = lit[len(prefix) + qlen : len(lit) - qlen]
        if qlen == 3 and "\n" in inner:
            # Multiline docstrings/prompts: translate as raw inner text.
            if "f" in prefix:
                continue
            has_translit_line = any(
                should_translate_text(ln.strip()) for ln in inner.splitlines() if ln.strip()
            )
            if not has_translit_line:
                continue
            st = pos_to_offset(starts, tok.start) + len(prefix) + qlen
            en = pos_to_offset(starts, tok.end) - qlen
            replacements.append(
                Replacement(
                    file_path=path,
                    start=st,
                    end=en,
                    source_text=inner,
                    encode_mode="raw",
                )
            )
            continue

        decoded: Optional[str] = None
        if "f" in prefix:
            decoded = decode_quoted_body(inner)
        else:
            try:
                val = ast.literal_eval(lit)
            except Exception:
                continue
            if not isinstance(val, str):
                continue
            decoded = val

        if not decoded:
            continue
        if " " not in decoded:
            continue
        if not should_translate_text(decoded):
            continue

        st = pos_to_offset(starts, tok.start) + len(prefix) + qlen
        en = pos_to_offset(starts, tok.end) - qlen
        replacements.append(
            Replacement(
                file_path=path,
                start=st,
                end=en,
                source_text=decoded,
                encode_mode="quote",
                quote_char=quote[0],
            )
        )

    return replacements


def collect_nonpython_replacements(path: Path, text: str) -> List[Replacement]:
    ext = path.suffix.lower()
    replacements: List[Replacement] = []
    offset = 0
    in_md_fence = False

    for line in text.splitlines(keepends=True):
        raw_line = line
        line_no_nl = raw_line.rstrip("\r\n")
        line_ending_len = len(raw_line) - len(line_no_nl)
        content_end_offset = offset + len(line_no_nl)

        if ext == ".md":
            stripped = line_no_nl.strip()
            if stripped.startswith("```"):
                in_md_fence = not in_md_fence
            if not in_md_fence and stripped and should_translate_text(stripped):
                # Keep markdown prefix markers.
                m = re.match(r"^(\s*(?:#{1,6}\s+|[-*+]\s+|\d+\.\s+)?)", line_no_nl)
                prefix = m.group(1) if m else ""
                core = line_no_nl[len(prefix) :]
                if core and should_translate_text(core):
                    st = offset + len(prefix)
                    en = content_end_offset
                    replacements.append(
                        Replacement(
                            file_path=path,
                            start=st,
                            end=en,
                            source_text=core,
                            encode_mode="plain",
                        )
                    )
            offset += len(raw_line)
            continue

        if ext in HASH_COMMENT_EXTS:
            idx = find_comment_start(line_no_nl, "#")
            if idx >= 0:
                tail = line_no_nl[idx + 1 :]
                stripped = tail.lstrip()
                if stripped and should_translate_text(stripped):
                    lead = len(tail) - len(stripped)
                    st = offset + idx + 1 + lead
                    en = st + len(stripped)
                    replacements.append(
                        Replacement(
                            file_path=path,
                            start=st,
                            end=en,
                            source_text=stripped,
                            encode_mode="plain",
                        )
                    )

        if ext in SLASH_COMMENT_EXTS:
            idx = find_comment_start(line_no_nl, "//")
            if idx >= 0:
                tail = line_no_nl[idx + 2 :]
                stripped = tail.lstrip()
                if stripped and should_translate_text(stripped):
                    lead = len(tail) - len(stripped)
                    st = offset + idx + 2 + lead
                    en = st + len(stripped)
                    replacements.append(
                        Replacement(
                            file_path=path,
                            start=st,
                            end=en,
                            source_text=stripped,
                            encode_mode="plain",
                        )
                    )

        if ext in QUOTED_STRING_EXTS:
            for rx, q in ((DOUBLE_QUOTE_RE, '"'), (SINGLE_QUOTE_RE, "'")):
                for m in rx.finditer(line_no_nl):
                    body = m.group(1)
                    decoded = decode_quoted_body(body)
                    if " " not in decoded:
                        continue
                    if not should_translate_text(decoded):
                        continue
                    st = offset + m.start(1)
                    en = offset + m.end(1)
                    replacements.append(
                        Replacement(
                            file_path=path,
                            start=st,
                            end=en,
                            source_text=decoded,
                            encode_mode="quote",
                            quote_char=q,
                        )
                    )

        if ext in HTML_EXTS:
            for m in HTML_TEXT_RE.finditer(line_no_nl):
                body = m.group(1)
                stripped = body.strip()
                if not stripped:
                    continue
                if not should_translate_text(stripped):
                    continue
                lead = len(body) - len(body.lstrip())
                trail = len(body) - len(body.rstrip())
                st = offset + m.start(1) + lead
                en = offset + m.end(1) - trail
                replacements.append(
                    Replacement(
                        file_path=path,
                        start=st,
                        end=en,
                        source_text=stripped,
                        encode_mode="plain",
                    )
                )

        offset += len(raw_line)
        _ = line_ending_len

    return replacements


def protect_placeholders(text: str) -> Tuple[str, Dict[str, str]]:
    mapping: Dict[str, str] = {}

    def _repl(m: re.Match[str]) -> str:
        key = f"ZZPH{len(mapping)}ZZ"
        mapping[key] = m.group(0)
        return key

    return PH_RE.sub(_repl, text), mapping


def restore_placeholders(text: str, mapping: Dict[str, str]) -> str:
    out = text
    for k, v in mapping.items():
        out = out.replace(k, v)
    return out


async def build_translation_map(texts: Iterable[str], batch_size: int = 40) -> Dict[str, str]:
    unique = sorted({t for t in texts if t and should_translate_text(t)})
    out: Dict[str, str] = {}
    if not unique:
        return out

    tr = Translator()
    i = 0
    while i < len(unique):
        batch = unique[i : i + batch_size]
        protected: List[str] = []
        maps: List[Dict[str, str]] = []
        for t in batch:
            p, m = protect_placeholders(t)
            protected.append(p)
            maps.append(m)

        try:
            translated = await tr.translate(protected, src="ru", dest="en")
        except Exception:
            # Fallback: per-item translation for robustness.
            translated = []
            for p in protected:
                try:
                    translated.append(await tr.translate(p, src="ru", dest="en"))
                except Exception:
                    translated.append(type("Obj", (), {"text": p})())

        if not isinstance(translated, list):
            translated = [translated]

        for original, tr_obj, mp in zip(batch, translated, maps):
            eng = (getattr(tr_obj, "text", "") or "").strip()
            if not eng:
                eng = original
            eng = restore_placeholders(eng, mp)
            out[original] = eng
        i += batch_size
    return out


def apply_replacements(
    path: Path, text: str, replacements: List[Replacement], translations: Dict[str, str]
) -> Tuple[str, int]:
    if not replacements:
        return text, 0

    chunks = list(text)
    applied = 0
    for rep in sorted(replacements, key=lambda r: (r.start, r.end), reverse=True):
        translated = translations.get(rep.source_text, rep.source_text)
        if not translated or translated == rep.source_text:
            continue

        replacement_text = translated
        if rep.encode_mode == "quote":
            replacement_text = encode_quoted_body(translated, rep.quote_char)
        elif rep.encode_mode == "raw":
            replacement_text = translated

        chunks[rep.start : rep.end] = list(replacement_text)
        applied += 1

    return "".join(chunks), applied


def read_text(path: Path) -> Optional[str]:
    for enc in ("utf-8", "utf-8-sig", "cp1251", "latin-1"):
        try:
            return path.read_text(encoding=enc)
        except Exception:
            continue
    return None


def write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8", newline="")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Translate transliterated Russian text into English.")
    p.add_argument("--root", type=Path, default=Path("."), help="Project root.")
    p.add_argument("--apply", action="store_true", help="Write changes to files.")
    p.add_argument(
        "--python-strings",
        action="store_true",
        help="Also translate simple one-line Python string literals (conservative).",
    )
    p.add_argument(
        "--extensions",
        nargs="*",
        default=sorted(DEFAULT_EXTENSIONS),
        help="Extensions to process (e.g. .py .md .js).",
    )
    p.add_argument(
        "--exclude-dir",
        nargs="*",
        default=sorted(DEFAULT_EXCLUDE_DIRS),
        help="Directory names to exclude.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    root = args.root.resolve()
    exts = {e.lower() if e.startswith(".") else f".{e.lower()}" for e in args.extensions}
    exclude = {d.lower() for d in args.exclude_dir}

    files = discover_files(root, exts, exclude)
    all_replacements: Dict[Path, List[Replacement]] = defaultdict(list)
    all_source_texts: List[str] = []
    file_texts: Dict[Path, str] = {}

    for fp in files:
        text = read_text(fp)
        if text is None:
            continue
        file_texts[fp] = text
        ext = fp.suffix.lower()
        if ext == ".py":
            reps = collect_python_replacements(fp, text, include_strings=bool(args.python_strings))
        else:
            reps = collect_nonpython_replacements(fp, text)
        if reps:
            all_replacements[fp].extend(reps)
            all_source_texts.extend(r.source_text for r in reps)

    translations = asyncio.run(build_translation_map(all_source_texts))

    changed_files = 0
    applied_count = 0
    for fp, reps in all_replacements.items():
        old = file_texts[fp]
        new, applied = apply_replacements(fp, old, reps, translations)
        if applied and new != old:
            changed_files += 1
            applied_count += applied
            if args.apply:
                write_text(fp, new)

    print(f"Scanned files: {len(files)}")
    print(f"Candidate replacements: {len(all_source_texts)}")
    print(f"Unique translated snippets: {len(translations)}")
    print(f"Changed files: {changed_files}")
    print(f"Applied replacements: {applied_count}")
    print(f"Mode: {'apply' if args.apply else 'dry-run'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
