# Agent OS Operator Notes

## Kak Ester prosit sebe agenta

1. Vybrat shablon (`template_id`) iz `/debug/garage/templates`.
2. Peredat tsel (`goal`) i imya (`name`) pri neobkhodimosti.
3. Sozdat cherez `tools/garage_make_agent.py` ili `POST /debug/garage/agents/create_from_template`.
4. Proverit `plan.json` i `README_agent.txt` v papke agenta.

## Kak Owner prosit Ester sdelat agenta

1. Utochnit tip zadachi (arkhivirovat, postroit plan, sobrat artefakt, proverit).
2. Vybrat blizhayshiy shablon iz pack v1.
3. Peredat chelovekochitaemuyu tsel v `--goal` (ili `goal` v API).
4. Zapustit `run_once` v bezopasnom rezhime i proverit outbox/journal.

## Chto vklyuchat dlya oracle/comm i pochemu eto opasno

- Po umolchaniyu `oracle` i `comm` vyklyucheny.
- Dlya `oracle` nuzhno odnovremenno:
  - vklyuchit `enable_oracle`,
  - otkryt oracle window,
  - proyti Volition allow.
- Dlya `comm` nuzhno vklyuchit `enable_comm` i imet razreshennoe comm window.
- Risk: setevye deystviya rasshiryayut poverkhnost ataki i mogut narushit offline-first profil; poetomu trebuetsya yavnoe okno i prichina.

