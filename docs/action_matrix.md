# Action Matrix (Iter37)

Offline-first Agent OS v0.1 for `D:\ester-project`.

## Core rule
- Ester core invokes agents.
- Agents invoke actions.
- Every action goes through `VolitionGate` before execution.

## Actions

| id | description | args schema (minimal) | IO roots (read/write) | risk | requires_volition |
|---|---|---|---|---|---|
| `fs.list` | List directory entries | `{"path":"str","limit":"int?"}` | read: repo root / write: none | low | yes |
| `fs.read` | Read local file (bounded bytes) | `{"path":"str","max_bytes":"int?"}` | read: repo root / write: none | low | yes |
| `fs.write` | Write local file | `{"path":"str","content":"str","dry_run":"bool?"}` | read: none / write: agent `artifacts` + builder roots | medium | yes |
| `fs.patch` | Replace/append file content | `{"path":"str","content":"str","mode":"replace\\|append?"}` | read: none / write: agent `artifacts` + builder roots | medium | yes |
| `scaffold.module` | Create module scaffold | `{"path":"str?","module":"str?"}` | read: none / write: builder roots | medium | yes |
| `memory.add_note` | Append memory note | `{"text":"str","tags":"list[str]?"}` | read: none / write: memory storage | low | yes |
| `messages.outbox.enqueue` | Queue local outbox message | `{"kind":"str","text":"str"}` | read: none / write: outbox storage | low | yes |
| `run_checks_offline` | Run offline checks script | `{}` | read: repo / write: check reports | medium | yes |
| `route_registry_check` | Validate route registry | `{}` | read: repo / write: none | low | yes |
| `route_return_lint` | Lint route returns | `{}` | read: repo / write: none | low | yes |
| `deps.report` | Produce deps report | `{}` | read: repo / write: report files | low | yes |
| `stubs.report` | Run stubs smoke check | `{}` | read: repo / write: stubs report files | low | yes |
| `oracle.openai.call` | Remote oracle call (default OFF) | `{"prompt":"str","window_id":"str","reason":"str"}` | read: none / write: network | high | yes |

## Agents

| name | role | actions | artifacts | budgets (default) |
|---|---|---|---|---|
| `archivist` | ingest -> memory | `fs.list`, `fs.read`, `memory.add_note`, `messages.outbox.enqueue` | `data/agents/<id>/artifacts/*` | `max_steps=6,max_ms=3000,window_sec=60` |
| `builder` | fs patch/write + scaffold | `fs.write`, `fs.patch`, `scaffold.module`, `fs.read`, `fs.list`, `memory.add_note` | `data/agents/<id>/artifacts/*` + allowed builder roots | `max_steps=8,max_ms=4000,window_sec=60` |
| `reviewer` | checks + reports | `run_checks_offline`, `route_registry_check`, `route_return_lint`, `deps.report`, `stubs.report` | check/report outputs + `artifacts` | `max_steps=8,max_ms=4500,window_sec=60` |

Ester core never delegates personality/core-creed changes to agents.

## Bridges

Explicit bridge (Ashby): regulator is valid only with observability.  
Agents cannot act outside Volition Gate + journal.

Hidden bridge #1 (Cover & Thomas): budgets/windows reduce plan entropy and keep signal useful.

Hidden bridge #2 (Guyton/Hall): deny/stop plus journal is negative feedback; without it system escalates into useless action tachycardia.

## Earth paragraph

Eto kak elektroschit v dome: mozhno podklyuchit mnogo stankov (agentov), no esli oni idut v obkhod avtomata (Volition Gate), provodka sgorit. Poetomu kazhdoe deystvie idet cherez avtomat, s limitom po toku (budget) i zapisyu, pochemu avtomat razreshil ili zapretil.
