# Acceptance Checklist (C/14…C/21)

**A/B pravilo:** po umolchaniyu `AB_MODE=A` (dry). Dlya zapisi otchetov/faylov deystviy ustanovit `AB_MODE=B`.

## 1. LM Studio Discovery (C/14)
- Otkryt `/admin/lmstudio_discovery`.
- Nazhat «Skanirovat»: vizhu naydennye puti/modeli, alias-predprosmotr.
- `AB_MODE=B` + «Primenit»: obnovlyaetsya `ESTER/portable/recommend.env`.  
Ozhidaemyy rezultat: alias-klyuchi `LLM_LOCAL_*` vidny na paneli ENV.

## 2. Local Scheduler (C/15)
- Otkryt `/admin/scheduler`. V A — dry-log.
- Polozhit `.txt` v `ESTER/inbox/` → «Skanirovat/Zapustit».  
Ozhidaemyy rezultat: v A — zhurnal shagov, v B — zadachi v `ESTER/state/queue/*.json`.

## 3. P2P FileMesh (C/16)
- Otkryt `/admin/p2p`. «Skanirovat».
- «Sobrat iz ocheredi» → poyavitsya payload v `ESTER/p2p/outbox/` (v B).
- Perenesti na drugoy uzel → «Importirovat» → elementy popali v lokalnuyu ochered.  
Ozhidaemyy rezultat: idempotentnyy import, `.done`-pometki.

## 4. Keys & Signatures (C/17)
- Otkryt `/admin/keys` → «Sozdat klyuchi» (v B), vizhu `meta.alg`, fingerprint.
- «Test podpisi»: ok.  
Ozhidaemyy rezultat: Ed25519 (ili HMAC fallback), `ESTER/keys/*`.

## 5. Peers (C/18)
- Otkryt `/admin/peers`. Importirovat rukopozhatie drugogo uzla.
- Vystavit doverie: trusted/unknown/blocked.  
Ozhidaemyy rezultat: `ESTER/state/peers.json` obnovlen.

## 6. Judge (C/19)
- Otkryt `/admin/judge`. Vvesti prompt → «Zaprosit».
- V A — moki; v B — lokalnye LM Studio po alias.  
Ozhidaemyy rezultat: spisok otvetov + finalnaya sborka.

## 7. Glue & Verify (C/20)
- `python tools/verify_routes.py` → ok=1, errors=0.
- Zapusk `python app.py` → `/admin/help` otkryvaetsya.

## 8. Final Snapshot (C/21)
- Otkryt `/admin/acceptance` → «Snyat snapshot».
- Libo `AB_MODE=B python tools/acceptance_snapshot.py --write`.  
Ozhidaemyy rezultat: `ESTER/reports/final_compliance.json` soderzhit:
  - spisok marshrutov (vklyuchaya vse admin-paneli),
  - SAFE-ENV,
  - artefakty i nalichie faylov,
  - `ok: true`, esli nichego ne otsutstvuet.
