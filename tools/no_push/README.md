# NoPush Guard (lokalnaya zaschita ot sluchaynykh pushey)

**Chto delaet:** stavit `pre-push` khuk Git, kotoryy **po umolchaniyu** blokiruet `git push`, poka vy *osoznanno* ne razreshite operatsiyu.

- Razreshenie na odin raz: `ALLOW_PUSH=1 git push`
- Postoyanno razreshit do otmeny: `touch .allow_push`
- Globalno zablokirovat: `touch .nopush` (sozdaetsya pri `install`)

## Ustanovka

```bash
bash scripts/no_push_guard.sh install
