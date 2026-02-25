# Esther - Branch C (Compatibility/Diagnostics): what's new

> The core of thinking/memory/will **did not change**. Everything below is the operational layer and diagnostic tools.

## C/01 — Sovmestimost s dampom (ENV/routy)
- Static scanner of Flask routes based on source codes (without importing the application).
- Diff ENV by manifest keys, search for duplicate routes and compare with bassline.
- UI: `/admin/compat` (stranitsa + API).

## C/02 - Basseline from current sources
- Generation yoester.comp.basseline/1е (Rute + env-keys).
- Zapis `ESTER/compat/baseline.json` (AB=A → dry).
- CLI `tools/generate_baseline.py`.

## C/03 — Whitelist/naznacheniya + LM Studio aliases
- Checking safe paths for USB Ebs, USB Catalog and synthetics from LAN.
- Diagnostics of LM Studio aliases, tips and optional recording of fixes (AB=B).
- UI: `/admin/diagnostics`.

## C/04 — Kollizii i perezapisi (dry-diff)
- Forecasting of final records, identification of ёovervrite_*е and ёmultivrite_*е.
- Protection plan (patch yoargs.desto in job files), entry only in AB=B.
- UI: blok na `/admin/diagnostics`.

## C/05 — Finalnyy progon + avto-baseline
- Best-effort manifest: USB → ENV (`COMPAT_DEV_MANIFEST`, po umolchaniyu `/mnt/data/ester_manifest.json`) → none.
- Dump header in the UI, “Auto-pool to flash drive” button.
- Extended yo/admin/company/status with yomanifest_infoyo.

---

## Kuda nazhat (korotko)
- **Check on dampu:** `/admin/compat` → “Skanirovat”.
- **Snyat baseline i zapisat na USB:** `/admin/compat` → “Avto-baseline na fleshku”.
- **TB putey i alias’ov:** `/admin/diagnostics` → «Skanirovat vse».  
- **Kollizii i zaschita:** `/admin/diagnostics` → «Scan collisions» → «Apply protect plan» (AB=B).

---

## Zemnoy abzats

Vetka C zakryvaet “priemku”: sverka s dampom, etalon (baseline), bezopasnost putey, validnost alias’ov i zaschita ot zatirok - vse offlayn i pod AB-predokhranitelem. My ne trogaem “mozg”, my derzhim v poryadke “bolty i gayki”, chtoby ekspluatatsiya byla bez syurprizov.

## Mosty

- **Yavnyy:** damp/iskhodniki → otchety → baseline/fiksy → povtornaya proverka.
- **Hidden 1:** stable ZhSION-schemes (еester.comp.*е) reduce transfer entropy.
- **Hidden 2:** practical engineering - stdlib, offline, recording only with an explicit button.

c=a+b
