
---

### `docs/Release_and_Key_Rotation.md`
```markdown
# Relizy i rotatsiya klyuchey

## SemVer
- **MAJOR** — nesovmestimye izmeneniya API/kontraktov (izbegaem).  
- **MINOR** — novye fichi bez polomok.  
- **PATCH** — fiksy/bezopasnost.

## Rotatsiya HMAC-klyuchey (P2P)
1) Dobavte novyy klyuch v `P2P_HMAC_KEYS` kak `main:NEW,prev:OLD`.  
2) Vydayte klientam `kid=main`. Staryy `prev` derzhite **N dney**.  
3) Uberite `prev` posle de-fakto migratsii.

## Povtory/nonce
- Ispolzuyte unikalnyy `X-Request-Id` na kazhdyy zapros.  
- Okno blokirovki povtorov: `P2P_REPLAY_TTL_SEC` (def. 600 sek).

## Migratsii BD
- SQLite — bez migratsiy (sozdanie tablits pri starte); dlya Postgres — alembic-skripty s temi zhe skhemami.

> ZEMNOY ABZATs: Klyuchi krutyatsya bez dauntayma; klienty migriruyut plavno; otkat — smenoy prioriteta klyucha.  
> c=a+b
