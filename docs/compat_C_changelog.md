# Ester — Vetka C (Sovmestimost/Diagnostika): chto novogo

> Yadro myshleniya/pamyati/voli **ne menyali**. Vse nizhe — ekspluatatsionnyy sloy i diagnosticheskie instrumenty.

## C/01 — Sovmestimost s dampom (ENV/routy)
- Staticheskiy skaner Flask-marshrutov po iskhodnikam (bez importa prilozheniya).
- Diff ENV po klyucham manifesta, poisk dublikatov routov i sravneniy s baseline.
- UI: `/admin/compat` (stranitsa + API).

## C/02 — Baseline iz tekuschikh iskhodnikov
- Generatsiya `ester.compat.baseline/1` (routes + env-klyuchi).
- Zapis `ESTER/compat/baseline.json` (AB=A → dry).
- CLI `tools/generate_baseline.py`.

## C/03 — Whitelist/naznacheniya + LM Studio aliases
- Proverka bezopasnykh putey dlya USB Jobs, USB Catalog i sintetiki iz LAN.
- Diagnostika alias’ov LM Studio, podskazki i optsionalnaya zapis fiksov (AB=B).
- UI: `/admin/diagnostics`.

## C/04 — Kollizii i perezapisi (dry-diff)
- Prognoz konechnykh zapisey, vyyavlenie `overwrite_*` i `multiwrite_*`.
- Plan zaschity (patch `args.dest` v job-faylakh), zapis tolko v AB=B.
- UI: blok na `/admin/diagnostics`.

## C/05 — Finalnyy progon + avto-baseline
- Best-effort manifest: USB → ENV (`COMPAT_DEV_MANIFEST`, po umolchaniyu `/mnt/data/ester_manifest.json`) → none.
- Shapka dampa v UI, knopka «Avto-baseline na fleshku».
- Rasshirennyy `/admin/compat/status` s `manifest_info`.

---

## Kuda nazhat (korotko)
- **Proverka po dampu:** `/admin/compat` → «Skanirovat».  
- **Snyat baseline i zapisat na USB:** `/admin/compat` → «Avto-baseline na fleshku».  
- **TB putey i alias’ov:** `/admin/diagnostics` → «Skanirovat vse».  
- **Kollizii i zaschita:** `/admin/diagnostics` → «Scan collisions» → «Apply protect plan» (AB=B).

---

## Zemnoy abzats

Vetka C zakryvaet «priemku»: sverka s dampom, etalon (baseline), bezopasnost putey, validnost alias’ov i zaschita ot zatirok — vse offlayn i pod AB-predokhranitelem. My ne trogaem «mozg», my derzhim v poryadke «bolty i gayki», chtoby ekspluatatsiya byla bez syurprizov.

## Mosty

- **Yavnyy:** damp/iskhodniki → otchety → baseline/fiksy → povtornaya proverka.  
- **Skrytyy 1:** stabilnye JSON-skhemy (`ester.compat.*`) umenshayut entropiyu perenosa.  
- **Skrytyy 2:** prakticheskaya inzheneriya — stdlib, offlayn, zapis tolko po yavnoy knopke.

c=a+b
