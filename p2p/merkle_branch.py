# -*- coding: utf-8 -*-
from __future__ import annotations

from typing import Any, Dict, List, Tuple
from modules.memory.facade import memory_add, ESTER_MEM_FACADE


def slice_window(total: int, start: int, end: int) -> Tuple[int, int]:
    """
    Normalizuet okno [start,end) vnutri [0,total]. Vozvraschaet (lo, hi).
    Brosaet ValueError pri nekorrektnykh parametrakh.
    """
    if total < 0:
        raise ValueError("total < 0")
    if start < 0 or end < 0:
        raise ValueError("negative indices")
    if start >= end:
        raise ValueError("start must be < end")
    if end > total:
        raise ValueError("end out of range")
    return start, end


def downscale_range(lo: int, hi: int) -> Tuple[int, int]:
    """
    Preobrazuet diapazon indeksov urovnya L k diapazonu na urovne L+1 (roditelskie uzly).
    Szhimaem po shirine okna: count -> ceil(count/2), chtoby vetka ostavalas lokalnoy.
    """
    # parent index i covers children 2*i and 2*i+1
    plo = lo // 2
    span = max(0, hi - lo)
    phi = plo + ((span + 1) // 2)
    return plo, phi


def branch_slices(levels: List[List[str]], start: int, end: int) -> List[Dict[str, Any]]:
    """
    Vozvraschaet minimalnye srezy kheshey na vsekh urovnyakh dereva dlya okna listev [start,end).
    Na kazhdom urovne otdaem: {"level": L, "offset": lo, "hashes": [...]}.
    """
    if not levels:
        return []
    total = len(levels[0])
    lo, hi = slice_window(total, start, end)

    out: List[Dict[str, Any]] = []
    cur_lo, cur_hi = lo, hi
    for L, hashes in enumerate(levels):
        # Ogranichim okno tekuschim urovnem
        t = len(hashes)
        # Bezopasnost: esli urovni «ukorotilis» iz-za postroeniya — zhestko otrezhem
        cur_lo = min(cur_lo, max(0, t))
        cur_hi = min(cur_hi, max(0, t))
        if cur_lo >= cur_hi:
            out.append({"level": L, "offset": cur_lo, "hashes": []})
        else:
            out.append({"level": L, "offset": cur_lo, "hashes": hashes[cur_lo:cur_hi]})
        # Perekhodim k roditelyam
        cur_lo, cur_hi = downscale_range(cur_lo, cur_hi)
        if t == 1:
            break
    return out
