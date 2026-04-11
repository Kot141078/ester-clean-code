# -*- coding: utf-8 -*-
"""output_filters - filtry vyvoda na baze TRS-metrik (best-effort).

Error from loga:
  '{' was never closed (__init__.py, line 19)

Eto pochti vsegda oznachaet, chto fayl `output_filters/__init__.py` (or analogichnyy, kotoryy realno gruzitsya)
okazalsya obrezan/skleen/isporchen tak, chto slovar/stroka ne zakrylis. V tvoem zagruzhennom variante
oshibka drugaya - tam prosto net `return`, no sintaksis tselyy. Poetomu ya dayu “kanonicheskiy” fayl,
kotoryy kompiliruetsya i rabotaet, a ty polozhish ego v to place, kotoroe realno importiruetsya:
- esli u tebya paket: <repo-root>\output_filters\__init__.py ← VAZhNO
- esli u tebya modul: <repo-root>\output_filters.py

API:
  filter_output(text: str) -> (cleaned_text: str, report: dict)

Mosty:
- Yavnyy most: validator.trs.measure_text/apply_rules → edinaya “sanitarnaya obrabotka” vyvoda pered otdachey polzovatelyu.
- Skrytye mosty:
  1) Infoteoriya ↔ ekspluatatsiya: score/issues = kompaktnyy kanal obratnoy svyazi (what imenno ukhudshaet tekst).
  2) Kibernetika ↔ nadezhnost: best-effort fallback - esli TRS-modul ne dostupen, kontur ne padaet.

ZEMNOY ABZATs: vnizu fayla."""

from __future__ import annotations

from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# --- optional dependency (best-effort) ---
_TRS_OK = True
_TRS_IMPORT_ERROR = ""

try:
    from validator.trs import apply_rules, measure_text  # type: ignore
except Exception as e:  # pragma: no cover
    _TRS_OK = False
    _TRS_IMPORT_ERROR = str(e)

    def measure_text(text: str) -> Tuple[float, List[Dict[str, Any]]]:  # type: ignore[override]
        # fallback: bez otsenki (neytralno)
        return 0.0, [{"rule": "trs_missing", "detail": _TRS_IMPORT_ERROR}]

    def apply_rules(text: str, score: float, issues: List[Dict[str, Any]]) -> str:  # type: ignore[override]
        # fallback: legkaya sanitarka, no bez agressii
        return (text or "").replace("\ufeff", "").strip()


def filter_output(text: str) -> Tuple[str, Dict[str, Any]]:
    """Applies TRS filters (or false) and returns (cleaned, report)."""
    score, issues = measure_text(text or "")
    cleaned = apply_rules(text or "", score, issues)
    report: Dict[str, Any] = {
        "ok": True,
        "trs_ok": _TRS_OK,
        "score": score,
        "issues": issues,
    }
    if not _TRS_OK:
        report["warning"] = "validator.trs is missing; fallback mode active"
        report["error"] = _TRS_IMPORT_ERROR
    return cleaned, report


__all__ = ["filter_output"]


ZEMNOY = """ZEMNOY ABZATs (anatomiya/inzheneriya):
Filtr vyvoda - kak marlya na vkhode v dykhatelnye puti: on ne lechit organizm, no zaderzhivaet krupnyy musor,
chtoby dalshe sistema ne “kashlyala” v samykh nepodkhodyaschikh mestakh (UI/logakh/integratsiyakh).
Glavnoe - chtoby marlya ne perekryvala potok polnostyu: poetomu fallback ne ronyaet modul, dazhe esli TRS net."""