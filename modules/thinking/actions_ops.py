# -*- coding: utf-8 -*-
"""modules/thinking/actions_ops.py - most deystviy v reestr dlya “voli” Ester.

Register action:
- forge.dry_run / forge.apply / forge.guarded_apply
-rollback.paths
- release.snapshot / release.torrent
- backup.run / backup.targets.set / backup.targets.get
- ethics.assess
- sos.assess/sos.trigger
- quorum.propose / quorum.vote / quorum.status
- scheduler.add / scheduler.tick / scheduler.list
- llm.complete
- capabilities.list
- imprint.verify

Mosty:
- Yavnyy: (Myslitelnyy konveyer ↔ Operatsii) edinyy vyzov “kind+args”.
- Skrytyy #1: (Ekonomika ↔ CostFence) vse shagi mozhno byudzhetirovat v playbook.
- Skrytyy #2: (Nadezhnost ↔ Guard) opasnye shagi mozhno oborachivat v guarded_apply/quorum/ethics.

Zemnoy abzats:
Kogda ruka tyanetsya k rychagu - etot fayl delaet rychagi vidimymi i odinakovymi dlya mozga Ester.

# c=a+b"""
from __future__ import annotations
from typing import Any, Dict
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

def _reg():
    try:
        from modules.thinking.action_registry import register  # type: ignore
    except Exception:
        return

    # ---- forge ----
    def a_forge_dry(args: Dict[str,Any]): 
        from modules.self.forge import dry_run
        return dry_run(list(args.get("changes") or []))
    register("forge.dry_run", {"changes":"list"}, {"ok":"bool"}, 15, a_forge_dry)

    def a_forge_apply(args: Dict[str,Any]):
        from modules.self.forge import apply
        return apply(list(args.get("changes") or []))
    register("forge.apply", {"changes":"list"}, {"ok":"bool"}, 30, a_forge_apply)

    def a_forge_guard(args: Dict[str,Any]):
        from modules.resilience.health import check
        from modules.self.forge import apply, dry_run
        from modules.resilience.rollback import rollback_paths
        plan = dry_run(list(args.get("changes") or []))
        if not plan.get("ok"): return {"ok": False, "error":"dry_run_failed", "plan": plan}
        res = apply(list(args.get("changes") or []))
        if not res.get("ok"):  return {"ok": False, "error":"apply_failed", "apply": res, "plan": plan}
        probe = check()
        if not probe.get("ok"):
            paths=[x.get("path") for x in (args.get("changes") or []) if isinstance(x,dict)]
            rb = rollback_paths(paths)
            return {"ok": False, "error":"health_failed_after_apply", "probe": probe, "rollback": rb, "plan": plan}
        return {"ok": True, "apply": res, "plan": plan, "probe": probe}
    register("forge.guarded_apply", {"changes":"list"}, {"ok":"bool"}, 45, a_forge_guard)

    # ---- rollback ----
    def a_rb(args: Dict[str,Any]):
        from modules.resilience.rollback import rollback_paths
        return rollback_paths(list(args.get("paths") or []))
    register("rollback.paths", {"paths":"list"}, {"ok":"bool"}, 15, a_rb)

    # ---- release / backup ----
    def a_snap(args: Dict[str,Any]):
        from modules.release.packager import snapshot
        return snapshot(list(args.get("roots") or ["modules","routes","middleware","services"]), str(args.get("name","ester")))
    register("release.snapshot", {"roots":"list","name":"str"}, {"ok":"bool"}, 60, a_snap)

    def a_tor(args: Dict[str,Any]):
        from modules.release.packager import make_torrent
        return make_torrent(str(args.get("manifest","")), list(args.get("announce") or []))
    register("release.torrent", {"manifest":"str","announce":"list"}, {"ok":"bool"}, 30, a_tor)

    def a_bkp_run(args: Dict[str,Any]):
        from modules.backup.local import run_backup
        return run_backup(list(args.get("roots") or []))
    register("backup.run", {"roots":"list"}, {"ok":"bool"}, 60, a_bkp_run)

    def a_bkp_set(args: Dict[str,Any]):
        from modules.backup.local import set_targets
        return set_targets(list(args.get("targets") or []))
    register("backup.targets.set", {"targets":"list"}, {"ok":"bool"}, 10, a_bkp_set)

    def a_bkp_get(args: Dict[str,Any]):
        from modules.backup.local import get_targets
        return get_targets()
    register("backup.targets.get", {}, {"ok":"bool"}, 5, a_bkp_get)

    # ---- ethics / sos ----
    def a_eth(args: Dict[str,Any]):
        from modules.ethics.guard import assess
        return assess(str(args.get("intent","")), args.get("context") or {})
    register("ethics.assess", {"intent":"str","context":"dict"}, {"ok":"bool"}, 5, a_eth)

    def a_sos_assess(args: Dict[str,Any]):
        from modules.sos.kit import assess
        return assess(str(args.get("signal","")), float(args.get("severity",0.0)), str(args.get("note","")), str(args.get("who","")))
    register("sos.assess", {"signal":"str","severity":"float","note":"str","who":"str"}, {"ok":"bool"}, 5, a_sos_assess)

    def a_sos_trigger(args: Dict[str,Any]):
        from modules.sos.kit import trigger
        return trigger(args.get("event") or {})
    register("sos.trigger", {"event":"dict"}, {"ok":"bool"}, 5, a_sos_trigger)

    # ---- quorum ----
    def a_q_prop(args: Dict[str,Any]):
        from modules.mesh.quorum import propose
        return propose(str(args.get("id","")), int(args.get("ttl",300)), args.get("payload") or {})
    register("quorum.propose", {"id":"str","ttl":"int","payload":"dict"}, {"ok":"bool"}, 5, a_q_prop)

    def a_q_vote(args: Dict[str,Any]):
        from modules.mesh.quorum import vote
        return vote(str(args.get("id","")), str(args.get("who","anon")), str(args.get("vote","abstain")))
    register("quorum.vote", {"id":"str","who":"str","vote":"str"}, {"ok":"bool"}, 5, a_q_vote)

    def a_q_stat(args: Dict[str,Any]):
        from modules.mesh.quorum import status
        return status()
    register("quorum.status", {}, {"ok":"bool"}, 5, a_q_stat)

    # ---- scheduler ----
    def a_sched_add(args: Dict[str,Any]):
        from modules.scheduler.core import add_job
        return add_job(str(args.get("kind","playbook")), str(args.get("spec","")), str(args.get("cron","*/5 * * * *")), str(args.get("note","")))
    register("scheduler.add", {"kind":"str","spec":"str","cron":"str","note":"str"}, {"ok":"bool"}, 10, a_sched_add)

    def a_sched_tick(args: Dict[str,Any]):
        from modules.scheduler.core import tick
        return tick()
    register("scheduler.tick", {}, {"ok":"bool"}, 10, a_sched_tick)

    def a_sched_list(args: Dict[str,Any]):
        from modules.scheduler.core import list_jobs
        return list_jobs()
    register("scheduler.list", {}, {"ok":"bool"}, 5, a_sched_list)

    # ---- llm broker ----
    def a_llm(args: Dict[str,Any]):
        from modules.llm.broker import complete
        return complete(str(args.get("provider","lmstudio")), str(args.get("model","")), str(args.get("prompt","")), int(args.get("max_tokens",256)), float(args.get("temperature",0.2)))
    register("llm.complete", {"provider":"str","model":"str","prompt":"str","max_tokens":"int","temperature":"float"}, {"ok":"bool"}, 30, a_llm)

    # ---- capabilities / imprint ----
    def a_caps(args: Dict[str,Any]):
        from modules.capabilities.registry import list_caps
        return list_caps()
    register("capabilities.list", {}, {"ok":"bool"}, 5, a_caps)

    def a_imprint_verify(args: Dict[str,Any]):
        from modules.self.imprint import verify
        return verify(args.get("text"), args.get("sha256"))
    register("imprint.verify", {"text":"str","sha256":"str"}, {"ok":"bool"}, 5, a_imprint_verify)

_reg()
# c=a+b