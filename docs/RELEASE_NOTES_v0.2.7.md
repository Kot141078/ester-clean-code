# Ester Clean Code — v0.2.7

Release date: 2026-04-26

## Scope

This release publishes the implementation-facing runtime work completed after `v0.2.6`.

The release keeps the public repository clean-code only. Live memory, local runtime logs, private `.env` values, tokens, and vector/passport stores are not included.

## Added

- Glitch Stack M1 sidecar contracts and adapters.
- Arbitration Review Layer sidecars for stop/persist, witness footprint, and review routing.
- Actor Grounding Layer sidecar.
- ARQ profile/capsule sidecar.
- Beacon Profile sidecar.
- SYNAPS protocol/config/auth sidecar.
- SYNAPS route adapter and listener bridge.
- SYNAPS dry-run-first probe tool.
- `run_ester_fixed.py` SYNAPS bridge wiring for the active runtime entrypoint.

## Safety Changes

- Manual SYNAPS health, chat, and bounded thought-request probes were verified in both directions with Lii before the stable tag.
- Probe tokens remain redacted in tool output.
- `metadata.probe=synaps_probe` thought requests do not write `[SISTER_THOUGHT_REQUEST]` background mirror records.
- `SISTER_AUTOCHAT=1` no longer starts an initiator by itself.
- Autochat initiator start now also requires `SISTER_AUTOCHAT_ARMED=1`.
- `SISTER_AUTOCHAT_ONESHOT=1` is available for future explicit one-shot windows.

## Not Included

- No live memory/passport/vector stores.
- No private `.env` files.
- No runtime logs or local backups.
- No enabled autochat window.

## Verification

Representative local checks before tagging:

```bash
python -m pytest tests/test_sister_autochat_guard.py tests/test_run_ester_synaps_contract.py tests/test_synaps_probe_tool.py tests/test_synaps_protocol.py tests/test_synaps_adapter.py tests/test_synaps_listener_bridge.py tests/test_beacon_profile.py tests/test_arq_sidecar.py tests/test_actor_grounding_layer.py tests/test_arbitration_review_layer.py tests/test_arbitration_review_witness.py tests/test_arbitration_review_routing.py tests/test_glitch_stack_m1.py tests/test_glitch_stack_store.py tests/test_glitch_stack_adapters.py tests/test_kg_beacons_query.py -q
```

```bash
python tools/check_public_release_safety.py --expected-tag v0.2.7
```

## Continuity

- `v0.2.6` remains unchanged for auditability.
- `v0.2.7` is the stable snapshot for the SYNAPS/sidecar implementation slice.
