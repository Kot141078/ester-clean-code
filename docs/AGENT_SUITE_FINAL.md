# Agent Suite — finalnaya sborka

**Chto gotovo**
- Vnutrenniy Agent Builder (opisanie → plan → fayly → (opts.) zapis).
- Sustainability Kit (cheklisty/metriki/brif → mini-plany).
- Report Console (MD/HTML → (opts.) zapis; shablon pechati v PDF).
- Activity Console (skan logov/statistika → daydzhest-plan).
- Activity → Report (iz aktivnosti pryamo v otchet).
- One-Click Green (tsel → bundle spec/plan/files/report).
- Indeks-stranitsa i itogovyy README, self-check-skript.

**Mosty**
- Yavnyy: (UX ↔ Mysli/Kaskad/Pravila) — vse paneli ispolzuyut `/thinking/act`, `/thinking/cascade/*`, `/rulehub/*` i obschiy JWT.
- Skrytyy #1: (Mysli ↔ Dokumentatsiya/Kodogeneratsiya) — zapis artefaktov idet cherez guarded_apply, s A/B-slotom i WRITE-flagom.
- Skrytyy #2: (Memory ↔ Audit) — sobytiya fiksiruyutsya zametkami v profile, dostupny v konsoli aktivnosti.

**Proverka**
1. `python tools/selfcheck_agent_suite.py --json` — vse eksheny, stranitsy i plany dolzhny byt `true`.  
2. Otkroy `docs/agent_suite_index.html`, proydi po panelyam, vypolni env-check i bazovye deystviya.  
3. Dlya zapisi vystav `ESTER_AGENT_BUILDER_AB=A` i `ESTER_AGENT_BUILDER_WRITE=1`; pri zhelanii vklyuchi RuleHub-preset `docs/agent_builder_rulehub_preset.yaml`.

**Zemnoy abzats**  
Pered toboy polnaya «pultovaya»: Ester sama opisyvaet i konstruiruet agentov, planiruet, sobiraet otchety, kontroliruet aktivnost i, pri razreshenii, vnosit izmeneniya v repozitoriy znaniy — ne menyaya suschestvuyuschie kontrakty.

c=a+b
