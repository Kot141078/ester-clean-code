# Agent Builder for Esther - safe use guide

## What is this
Mini-nadstroyka, pozvolyayuschaya Ester opisyvat, planirovat i sobirat agentov po tselyam - bez izmeneniya suschestvuyuschikh kontraktov. UI obraschaetsya k imeyuschimsya ruchkam `/thinking/act`, `/thinking/cascade/*`, `/rulehub/*`, avtorizatsiya vypolnyaetsya cherez obschiy mekhanizm JWT iz adminki.
  
**Mosty**  
- Yavnyy: (UX ↔ Mysli/Kaskad) - knopki v `docs/agent_builder.html` vyzyvayut `/thinking/act`, `/thinking/cascade/execute`.
- Skrytyy #1: (UX ↔ RuleHub) - tot zhe ekran pozvolyaet chitat/sokhranyat YAML cherez `/rulehub/config`.
- Skrytyy #2: (UX ↔ Avtorizatsiya) - edinyy JWT-potok iz `static/admin.js`.

## Bezopasnye rezhimy (A/B + WRITE)
- `ESTER_AGENT_BUILDER_AB`: `A` (defolt, bezopasnyy), `B` (eksperiment).  
- ёSTER_AGENT_BUILDER_WRITE: ё0е (default - writing is prohibited), е1е (allow writing).
The RuleNov policy (from the preset) additionally checks: slot=A, WRITE=1 and the absence of conflicts - otherwise the actions remain in the preview.

## Rabochiy potok
1. Zadayte tsel i auditoriyu → “Opisat agenta”.
2. «Sformirovat plan» → (pri zhelanii) «Vypolnit plan» — dry-run.  
3. «Sformirovat fayly (preview)» — vidite tochnyy spisok artefaktov.  
4. If you make a conscious decision, enable the entry (еESTER_AGENT_BUILDER_WRITE=1е, slot=A) and “Apply files”.
5. If necessary, use RuleNov-preset to unify and insure the procedure.

## Gde lezhit UI
- `docs/agent_builder.html` — staticheskaya panel (podobno drugim dokumentam v `docs/`) :contentReference[oaicite:3]{index=3}.  
- Skript: `static/admin_agent_builder.js`.  
- General ZhVT-helper: estatik/admin.yse (already in the project): contentReference:chchTsZF0Z.

## Zemnoy abzats
Eto praktichnyy “pult” dlya Ester: vy formuliruete tsel - ona sobiraet description, plan i prevyu faylov; dalee, pri yavnom razreshenii i pod prismotrom RuleHub, bezopasno primenyaet izmeneniya. Nothing lishnego: vse kontrakty prezhnie, a upravlenie - znakomymi knopkami.
  
c=a+b
