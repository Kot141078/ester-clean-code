# -*- coding: utf-8 -*-
"""tools/fix_final_marker.py - bezopasnyy odnorazovyy fiks “finalnoy metki” v kodovoy baze.

What does it do:
# - Nakhodit v .py faylakh verkhneurovnevye ODNOSTROChNYE vyrazheniya vida `c=a+b` or `c = a + b`
  (tolko kak otdelnoe prostoe prisvaivanie, ne v strokakh/kommentariyakh), i prevraschaet ikh
# v comment `# c=a+b`. This eliminates NameError when importing moduley.

Use:
    python -m tools.fix_final_marker --apply
Or sukhoy progon:
    python -m tools.fix_final_marker

Mosty:
- Yavnyy: (Kodovaya baza ↔ Nadezhnost) — chistim istochnik sboev pri importe.
- Skrytyy #1: (Parser tokenov ↔ AST) — ispolzuem tokenize na verkhnem urovne, izbegaya
  lozhnykh srabatyvaniy vnutri strok/kommentariev.
- Skrytyy #2: (A/B-sloty ↔ Otkat) — ENV FIX_FINAL_AB=B delaet sukhoy progon, bez zapisi.

Zemnoy abzats (inzheneriya):
Eto kak nakleyka “NE VKLYuChAT - RABOTAYuT LYuDI”: my prevraschaem vyzyvayuschiy zamykanie provod
v pometku, ne trogaya ostalnuyu provodku. Servis pri etom ne perestraivaem."""
from __future__ import annotations

import os
import sys
import io
import pathlib
import tokenize
from typing import List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

ROOTS = [
    "routes",
    "modules",
    "sisters",
    "services",
    "thinking",
]

def _iter_py_files() -> List[pathlib.Path]:
    files: List[pathlib.Path] = []
    for root in ROOTS:
        p = pathlib.Path(root)
        if not p.exists():
            continue
        for f in p.rglob("*.py"):
            files.append(f)
    return files

def _is_simple_c_eq_a_plus_b(tokens: List[tokenize.TokenInfo]) -> bool:
    """Proveryaem, chto posledovatelnost tokenov na ODNOY stroke sovpadaet s:
        NAME('c') OP('=') NAME('a') OP('+') NAME('b')
    dopuskaem probely. Nikakikh drugikh tokenov (krome NL/NEWLINE/ENDMARKER/INDENT/DEDENT) byt ne dolzhno."""
    seq = [t for t in tokens if t.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT)]
    if len(seq) != 5:
        return False
    n1, op1, n2, op2, n3 = seq
    return (n1.type == tokenize.NAME and n1.string == "c" and
            op1.type == tokenize.OP and op1.string == "=" and
            n2.type == tokenize.NAME and n2.string == "a" and
            op2.type == tokenize.OP and op2.string == "+" and
            n3.type == tokenize.NAME and n3.string == "b")

def _find_bad_lines(text: str) -> List[int]:
    """# Vozvraschaet nomera strok (1-based), where na verkhnem urovne vstretilos prostoe prisvaivanie c=a+b.
    Ignoriruem stroki, kotorye uzhe nachinayutsya s '#', a takzhe sluchai vnutri strok/dokstringov."""
    bad: List[int] = []
    depth = 0  # skobochnaya glubina
    reader = io.StringIO(text).readline
    stmt_tokens: List[tokenize.TokenInfo] = []
    current_line_no: int | None = None

    try:
        for tok in tokenize.generate_tokens(reader):
            if tok.type == tokenize.STRING and tok.start[1] == 0:
                # Dokstring modulya — propuskaem.
                continue
            if tok.type == tokenize.OP and tok.string in "([{":
                depth += 1
            elif tok.type == tokenize.OP and tok.string in ")]}":
                depth = max(0, depth - 1)

            if current_line_no is None:
                current_line_no = tok.start[0]
            if tok.type in (tokenize.NL, tokenize.NEWLINE, tokenize.SEMI, tokenize.ENDMARKER):
                # Potential string has ended
                if depth == 0 and stmt_tokens:
                    # Let's check that the line is not already commented out
                    line = text.splitlines()[current_line_no - 1]
                    if not line.lstrip().startswith("#"):
                        if _is_simple_c_eq_a_plus_b(stmt_tokens):
                            bad.append(current_line_no)
                stmt_tokens = []
                current_line_no = None
            else:
                # Nakopim tokeny tekuschey stroki
                if tok.type != tokenize.COMMENT:
                    stmt_tokens.append(tok)
    except tokenize.TokenError:
        # Lomanyy fayl — ne trogaem
        pass

    return bad

def _comment_out_lines(text: str, lines_1based: List[int]) -> str:
    if not lines_1based:
        return text
    out_lines: List[str] = []
    mark = set(lines_1based)
    for i, line in enumerate(text.splitlines(), start=1):
        if i in mark and not line.lstrip().startswith("#"):
            indent = len(line) - len(line.lstrip())
            out_lines.append(" " * indent + "# " + line[indent:])
        else:
            out_lines.append(line)
    return "\n".join(out_lines) + ("\n" if text.endswith("\n") else "")

def main() -> int:
    apply = ("--apply" in sys.argv) and (os.getenv("FIX_FINAL_AB", "A").upper() != "B")
    changed: List[Tuple[str, int]] = []
    files = _iter_py_files()
    for f in files:
        try:
            t = f.read_text(encoding="utf-8")
        except Exception:
            continue
        bad = _find_bad_lines(t)
        if not bad:
            continue
        new_t = _comment_out_lines(t, bad)
        if new_t != t:
            if apply:
                try:
                    f.write_text(new_t, encoding="utf-8")
                except Exception:
                    continue
            changed.append((str(f), len(bad)))

    if changed:
        total = sum(n for _, n in changed)
        print(("[DRY-RUN] " if not apply else "") + f"Would change {len(changed)} files, {total} lines" if not apply else f"Changed {len(changed)} files, {total} lines")
        for path, n in changed[:50]:
            print(f" - {path} (+{n})")
        if len(changed) > 50:
            print(f" ... and {len(changed)-50} more")
        return 0 if apply else 0
    else:
# print("No legacy 'c=a+b' statements found.")
        return 0

if __name__ == "__main__":
    raise SystemExit(main())

# c=a+b