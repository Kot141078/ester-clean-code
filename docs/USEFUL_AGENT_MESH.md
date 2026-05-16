# Useful Agent Mesh

Ester's useful agent mesh is a bounded replacement for the old open-ended swarm prewarm loop.

The mesh keeps a stable local roster of worker roles:

- `sentinel`
- `tester`
- `auditor`
- `reader`
- `archivist`
- `judge_assistant`
- `executor`
- `orchestrator_limited`

Each role is registered as a local CLI worker under the C-Governed CLI Agent Mesh rules:

- registration is not permission;
- capability is not authority;
- every scheduled run carries a task contract;
- network is denied by default;
- secrets and private memory are denied;
- direct memory writes are denied;
- outputs are sandbox artifacts and operational outbox notes;
- legacy swarm expansion stays disabled.

## Runtime Controls

Enable the bounded mesh:

```text
ESTER_USEFUL_AGENT_MESH_ENABLED=1
ESTER_USEFUL_AGENT_MESH_INTERVAL_SEC=180
ESTER_USEFUL_AGENT_MESH_TASK_INTERVAL_SEC=900
ESTER_USEFUL_AGENT_MESH_MAX_ENQUEUE_PER_TICK=2
ESTER_USEFUL_AGENT_MESH_MAX_LIVE=2
ESTER_USEFUL_AGENT_MESH_DRAIN_BATCH=2
```

Keep the legacy growth paths off unless they are redesigned under the same contract layer:

```text
ESTER_AGENT_SWARM_ENABLED=0
ESTER_AGENT_SUPERVISOR_ENABLED=0
ESTER_AGENT_ROLE_POOL_ENABLED=0
ESTER_AGENT_ROLE_PREWARM_ENABLED=0
ESTER_AGENT_WINDOW_AUTO_ENABLED=0
ESTER_PROACTIVITY_LEGACY_AGENT_QUEUE_ENABLED=0
```

The useful mesh scheduler opens its own short execution window only when it has queued bounded work.

When the useful mesh is enabled, legacy `proactivity_enqueue:*` agent queue writes are held in `plan_only` unless
`ESTER_PROACTIVITY_LEGACY_AGENT_QUEUE_ENABLED=1` is set. The lower-level queue also rejects direct proactivity
enqueue attempts that do not carry `plan.meta.governed_mesh=true`.

## Files

The mesh writes local operational state under:

```text
data/garage/useful_mesh/
```

Role reports are written only inside the agent sandbox:

```text
data/garage/agents/<agent_id>/sandbox/governed_mesh/
```

These reports are not memory. They are operational artifacts behind the memory gate.

## Status

Use:

```text
GET /agents/useful_mesh/status
```

Admin-only maintenance endpoints:

```text
POST /debug/agents/useful_mesh/reconcile
POST /debug/agents/useful_mesh/maintain
```

## Conformance

The first implementation target is conservative:

- handshake: `HSP-3`
- sandbox: `SWP-2`
- mesh: `CGAM-2`

This gives Ester useful bounded hands without restoring uncontrolled swarm behavior.
