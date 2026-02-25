# Acceptance Checklist (C/14…C/21)

**A/B rule:** by default eAB_MODE=Ae (dry). To record reports/action files, set eAB_MODE=Бе.

## 1. LM Studio Discovery (C/14)
- Otkryt `/admin/lmstudio_discovery`.
- Click “Scan”: I see the found paths/models, alias preview.
- eAB_MODE = Be + “Apply”: updated eESTER/portable/recommended.enve.
Expected result: alias keys ёLLM_LOCAL_*е are visible in the ENV panel.

## 2. Local Scheduler (C/15)
- Otkryt `/admin/scheduler`. V A — dry-log.
- Polozhit `.txt` v `ESTER/inbox/` → “Skanirovat/Zapustit”.
Expected result: in A - a log of steps, in B - tasks in eESTER/article/queue/*.jsonyo.

## 3. P2P FileMesh (C/16)
- Otkryt `/admin/p2p`. «Skanirovat».
- “Sobrat iz ocheredi” → poyavitsya payload v `ESTER/p2p/outbox/` (v B).
- Move to another node → “Import” → elements are added to the local queue.
Ozhidaemyy rezultat: idempotentnyy import, `.done`-pometki.

## 4. Keys & Signatures (C/17)
- Open `/admin/keys` → “Sozdat klyuchi” (v B), vizhu `meta.alg`, fingerprint.
- «Test podpisi»: ok.  
Ozhidaemyy rezultat: Ed25519 (ili HMAC fallback), `ESTER/keys/*`.

## 5. Peers (C/18)
- Otkryt `/admin/peers`. Importirovat rukopozhatie drugogo uzla.
- Vystavit doverie: trusted/unknown/blocked.  
Expected result: eESTER/article/pers.jsonyo updated.

## 6. Judge (C/19)
- Open `/admin/judge`. Vvesti prompt → “Request”.
- V A — moki; v B — lokalnye LM Studio po alias.  
Expected result: list of answers + final assembly.

## 7. Glue & Verify (C/20)
- `python tools/verify_routes.py` → ok=1, errors=0.
- Zapusk `python app.py` → `/admin/help` otkryvaetsya.

## 8. Final Snapshot (C/21)
- Open `/admin/acceptance` → “Snyat snapshot”.
- Libo `AB_MODE=B python tools/acceptance_snapshot.py --write`.  
Expected result: eESTER/reports/final_complianke.jsonyo contains:
  - list of routes (including all admin panels),
  - SAFE-ENV,
  - artefakty i nalichie faylov,
  - yook: three if nothing is missing.
