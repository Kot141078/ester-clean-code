# Ester — Agent Suite (Builder, KIT, Report, Activity, One-Click)

Etot fayl — dorozhnaya karta po novym panelyam i deystviyam, dobavlennym v ramkakh AgentBuilderCore.

**Mosty**
- Yavnyy: (Dokumentatsiya ↔ UX) — opisyvaet, gde lezhat paneli i kak oni obraschayutsya k suschestvuyuschim ruchkam `/thinking/act`, `/thinking/cascade/*`, `/rulehub/*`.
- Skrytyy #1: (Dokumentatsiya ↔ Bezopasnost) — fiksiruet A/B-rezhim i WRITE-flag dlya guarded_apply (bez izmeneniya kontraktov).
- Skrytyy #2: (Dokumentatsiya ↔ Memory) — rekomenduemye zametki/profile dlya audita, sinkhronno s tem, chto uzhe delaet kaskad.

---

## Karta paneley (vse — staticheskie dokumenty v `docs/`)

- `agent_builder.html` — konstruktor agentov poverkh `/thinking/act` i kaskada.  
- `agent_builder_kit.html` — Sustainability Kit (cheklisty, metriki, mini-plan).  
- `agent_report.html` — sborka MD/HTML-otchetov, zapis cherez guarded_apply.  
- `agent_activity.html` — prosmotr aktivnosti Builder/KIT/Report + daydzhest-plan.  
- `activity_to_report.html` — «aktivnost → otchet» (MD/HTML + optsionalnaya zapis).  
- `oneclick_green.html` — One-Click Green: iz tseli → bundle (spec/plan/files/report).

Vse paneli ispolzuyut obschiy JWT-khelper iz `static/admin.js` (localStorage: `ester.jwt`, zagolovok `Authorization: Bearer ...`).

---

## ENV-pereklyuchateli (po umolchaniyu bezopasno)

- `ESTER_AGENT_BUILDER_AB`: `"A"` (defolt, bezopasnyy)/`"B"` (eksperiment).  
- `ESTER_AGENT_BUILDER_WRITE`: `0` (defolt — zapis zapreschena)/`1` (razreshit zapis).  
Politiki RuleHub mogut dopolnitelno prinuzhdat prevyu i zhurnalirovat sobytiya.

---

## Bystryy chek-list registratsii v menyu/dokakh (bez izmeneniya servernykh marshrutov)

1. **Ssylki v indeks-dokakh**  
   - Dobavte ssylki na stranitsy iz `docs/agent_suite_index.html` v vash glavnyy indeks dokumentatsii (naprimer, v suschestvuyuschiy `docs/index.html`, esli on ispolzuetsya v proekte).  
   - Struktura ssylok otnositelnaya, t.k. vse stranitsy lezhat v `docs/`.

2. **Navigatsiya v adminke (optsionalno)**  
   - Esli u vas est sobstvennaya «vitrina» ssylok v UI/portale, dobavte punkty na perechislennye HTML.  
   - Servernye marshruty ne trebuyutsya — eto staticheskie fayly.

3. **RuleHub-presety**  
   - Pri neobkhodimosti vklyuchite preset `docs/agent_builder_rulehub_preset.yaml` cherez stranitsu RuleHub (chtenie/sokhranenie YAML uzhe podderzhivaetsya suschestvuyuschey adminkoy).

4. **Smoke-test**  
   - Otkroyte lyubuyu panel → «Proverit okruzhenie» (pokazhet AB-slot i status RuleHub).  
   - Vypolnite bazovye deystviya: list/describe/plan/execute ili compose/save (v prevyu).  
   - Dlya zapisi vklyuchite **oba** usloviya: `AB=A` i `WRITE=1` (i podtverdite politiku, esli ona vklyuchena).

---

## Zemnoy abzats

Eto «oblozhka» k novomu funktsionalu: odin README i edinyy indeks navigatsii. Polzovatelyu — gde i klikat; Ester — s prezhnimi kontraktami, bez syurprizov. A/B i WRITE delayut samoizmeneniya bezopasnymi po umolchaniyu.

c=a+b.
