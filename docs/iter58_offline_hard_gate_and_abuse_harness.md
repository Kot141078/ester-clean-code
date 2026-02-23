# Iter58: Offline Hard Gate + Abuse Harness

## Summary

Iter58 adds a runtime hard gate for outbound networking and a single abuse harness that continuously validates deny/quarantine/crypto-integrity behavior in offline mode.

## NetworkDeny Design

Core module: `modules/runtime/network_deny.py`.

What it does:

- Installs socket-level deny hooks for outbound traffic:
  - `socket.socket.connect`
  - `socket.socket.connect_ex`
  - `socket.create_connection`
- Enforces allowlist-only policy.
- Logs deny events into append-only JSONL (default `data/integrity/net_deny.jsonl`).
- Exposes runtime stats:
  - install status
  - active mode (`A`/`B`)
  - allow rules
  - deny counters and last deny event

## Allow Rules

Defaults:

- CIDRs: `127.0.0.1/32`, `::1/128`
- Hosts: `localhost`

Config:

- `ESTER_OFFLINE=1`
- `ESTER_NET_ALLOW_CIDRS="127.0.0.1/32,::1/128"`
- `ESTER_NET_ALLOW_HOSTS="localhost"`
- `ESTER_NET_DENY_MODE="A|B"`
- `ESTER_NET_DENY_LOG_JSONL=1`

Behavior:

- Non-allowlisted outbound targets are denied before real connect.
- Slot A:
  - socket-level hard gate.
  - DNS names are resolved and denied by resolved IP if not allowlisted.
- Slot B:
  - same socket-level hard gate plus extra hooks:
    - `urllib.request.urlopen`
    - `http.client.HTTPConnection.connect`
  - non-allowlisted DNS names are denied as `DNS_NAME_DENIED`.
- If Slot B extra hooks become unstable, runtime auto-rolls back to Slot A in-process while keeping socket-level deny active.

## Boot Integration

NetworkDeny is installed early from `modules/__init__.py` when offline is enabled, so app and tools importing `modules.*` run under the same hard gate.

## Runtime Status

`/debug/runtime/status` (from `modules/runtime/status_iter18.py`) now includes:

- `network.offline`
- `network.deny_installed`
- `network.slot`
- `network.mode`
- `network.allow_cidrs`
- `network.allow_hosts`
- `network.deny_count`
- `network.last_deny`

## Smokes

### `tools/network_deny_smoke.py`

Validates:

1. Hard gate installed in offline mode.
2. Loopback allowed (`127.0.0.1` TCP local server).
3. Outbound denied deterministically (`1.1.1.1:80`).
4. Deny counters and JSONL log are updated.
5. Runtime status exposes installed network deny state.

### `tools/abuse_harness_smoke.py`

Runs one orchestrated pass across four attack classes:

1. Capability escalation + clear requires evidence/L4W.
2. Allowlist tamper + drift/quarantine path.
3. Roster log forgery detection.
4. Bundle tamper detection.

Exit code is `0` only when all subtests match expected deny/fail-closed outcomes.

## Offline Checks Wiring

`tools/run_checks_offline.ps1` now runs:

- `python -B tools/network_deny_smoke.py`
- `python -B tools/abuse_harness_smoke.py`

and sets `ESTER_OFFLINE=1` in safe defaults.

## Bridges

- Explicit bridge (Ashby): hard gate increases controllability because outbound channel is physically closed and observable, independent of agent intent.
- Hidden bridge #1 (information theory): deny-log is the feedback channel; without it, offline state is unverifiable.
- Hidden bridge #2 (anatomy): NetworkDeny is skin barrier, abuse harness is immune-system challenge testing.

## Earth Paragraph

On a factory floor, policy saying "do not power this machine" is weaker than a real relay that physically cuts the line. NetworkDeny is that relay for outbound network. Abuse harness is scheduled emergency drills: simulate escalation/tamper/forgery and verify the system blocks, isolates, and requires evidence before restoring operation.

