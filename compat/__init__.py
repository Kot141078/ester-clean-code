# -*- coding: utf-8 -*-
"""compat - layer sovmestimosti dlya Ester.
Naznachenie: ne menyaya starye importy/puti, akkuratno podlozhit aliasy i myagkie patchi:
- sopostavit starye prostranstva imen (memory, agents, quality, graph, llm, ...)
  s realnym tree modules.*;
- dobavit otsutstvuyuschie simvoly, ozhidaemye kodom (napr. modules.quality.guard.enable);
- sgladit nesovmestimosti storonnikh paketov (flask_jwt_extended v4).

MOSTY:
- Yavnyy: Teoriya informatsii (Kover–Tomas) → kanal s noise. Aliasy umenshayut “shum” putey, sokhranyaya poleznyy signal (rabochie importy), chto snizhaet veroyatnost oshibki pri dekodirovanii (importe).
- Skrytyy 1: Bayes (Dzheynes) → aposteriornaya pravdopodobnost. Esli modul suschestvuet pod modules.*, alias uvelichivaet veroyatnost uspeshnogo importa “starogo” imeni.
- Skrytyy 2: Kibernetika (Eshbi) → regulyator raznoobraziya. Szhimaem raznomastnye importy do upravlyaemogo mnozhestva cherez tsentralizovannyy kontroller.

ZEMNOY ABZATs:
Eto kak kollektor dlya kabeley v stoyke: kuda by staryy provod ni byl protyanut, kollektor perenapravit ego na pravilnyy port. Svet ne morgaet, stoyka ne padaet."""
from __future__ import annotations
import importlib
import sys
import types
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# --- Karta aliasov moduley (levo → pravo). K tochechnym imenam sozdaem roditeley avtomaticheski.
ALIASES = {
    # Top-urovni, kotorye v dampe realno zhivut pod modules.*
    "memory": "modules.memory",
    "agents": "modules.agents",
    "quality": "modules.quality",
    "graph": "modules.graph",
    "llm": "modules.llm",
    "subconscious": "modules.subconscious",
    "lan": "modules.lan",
    "usb": "modules.usb",
    "storage": "modules.storage",
    "transport": "modules.transport",
    "compliance": "modules.compliance",
    "acceptance": "modules.acceptance",
    "env": "modules.env",
    "jobs": "modules.jobs",
    "judge": "modules.judge",
    "registry": "modules.registry",
    "reports": "modules.reports",
    "selfmanage": "modules.selfmanage",
    # Frequent typos/variants
    "listners": "listeners",  # if somewhere the name is wrong, we will transfer it to the real listeners package
    # Point paths that were found in the logs
    "graph.dag_engine": "modules.graph.dag_engine",
    "subconscious.engine": "modules.subconscious.engine",
    "llm.autoconfig_settings": "modules.llm.autoconfig_settings",
    "selfmanage.sync_profiles": "modules.selfmanage.sync_profiles",
}

def _ensure_parent(pkg: str) -> None:
    """Creates missing parent packages in sys.modules (empty namespace-modules)."""
    parts = pkg.split(".")
    for i in range(1, len(parts)):
        name = ".".join(parts[:i])
        if name not in sys.modules:
            m = types.ModuleType(name)
            m.__path__ = []  # type: ignore[attr-defined]
            sys.modules[name] = m

def _alias_module(old: str, new: str) -> None:
    """Links the old module to the real new module (if it is imported). Otherwise, it creates an empty namespace."""
    try:
        real_mod = importlib.import_module(new)
        _ensure_parent(old)
        sys.modules[old] = real_mod
        # We also link submodules (old.*) on the fly through Python findry - we’ll leave it to Pithuna, we won’t overcomplicate it here
    except Exception:
        # If there is no target, we create an empty module so that the old import itself does not crash the process
        _ensure_parent(old)
        if old not in sys.modules:
            fallback = types.ModuleType(old)
            fallback.__dict__["__compat_missing__"] = new
            sys.modules[old] = fallback

def _install_aliases():
    for left, right in ALIASES.items():
        _alias_module(left, right)

# --- Soft patches for known incompatibilities -------------------------------

def _patch_quality_guard_enable():
    """If there is modules.kalita.guard, but it does not have enable/disable, we will add neutral tires."""
    try:
        mod = importlib.import_module("modules.quality.guard")
    except Exception:
        return
    if not hasattr(mod, "enable"):
        def enable(*args, **kwargs):
            # Neutral quality switch (does nothing by default)
            return {"ok": True, "mode": "compat", "feature": "quality_guard", "enabled": True}
        mod.enable = enable  # type: ignore[attr-defined]
    if not hasattr(mod, "disable"):
        def disable(*args, **kwargs):
            return {"ok": True, "mode": "compat", "feature": "quality_guard", "enabled": False}
        mod.disable = disable  # type: ignore[attr-defined]

def _patch_messaging_telegram_adapter():
    """If there is a messaging.telegram_adapter, but there is no TelegramAdapter, we will add a safe stub class."""
    try:
        mod = importlib.import_module("messaging.telegram_adapter")
    except Exception:
        return
    if not hasattr(mod, "TelegramAdapter"):
        class TelegramAdapter:  # type: ignore
            def __init__(self, *args, **kwargs):
                self.ready = False
                self.reason = "compat: TelegramAdapter not configured/implemented"
            def send(self, *args, **kwargs):
                raise RuntimeError(self.reason)
            def health(self):
                return {"ok": False, "reason": self.reason}
        mod.TelegramAdapter = TelegramAdapter  # type: ignore[attr-defined]

def _patch_flask_jwt_extended():
    """We add verifs_zhvt_in_reguest_optional if the library removed/renamed it."""
    try:
        fj = importlib.import_module("flask_jwt_extended")
    except Exception:
        return
    if not hasattr(fj, "verify_jwt_in_request_optional"):
        # Let's try to assemble the functionality through verifications_zhvt_in_reguest (optional=Three)
        def verify_jwt_in_request_optional(*args, **kwargs):
            try:
                if hasattr(fj, "verify_jwt_in_request"):
                    return fj.verify_jwt_in_request(optional=True)  # type: ignore
            except Exception:
                # As a last resort, we do nothing (the route will not require gas transportation)
                return None
        fj.verify_jwt_in_request_optional = verify_jwt_in_request_optional  # type: ignore[attr-defined]

def enable():
    """The main point of inclusion of the compatibility layer."""
    _install_aliases()
    _patch_quality_guard_enable()
    _patch_messaging_telegram_adapter()
    _patch_flask_jwt_extended()
    return True

# Avtozapusk pri importe compat
try:
    enable()
except Exception:
    # We never drop the process at the compatibility level
    pass

# c=a+b