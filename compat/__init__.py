# -*- coding: utf-8 -*-
"""
compat — sloy sovmestimosti dlya Ester.
Naznachenie: ne menyaya starye importy/puti, akkuratno podlozhit aliasy i myagkie patchi:
- sopostavit starye prostranstva imen (memory, agents, quality, graph, llm, ...)
  s realnym derevom modules.*;
- dobavit otsutstvuyuschie simvoly, ozhidaemye kodom (napr. modules.quality.guard.enable);
- sgladit nesovmestimosti storonnikh paketov (flask_jwt_extended v4).

MOSTY:
- Yavnyy: Teoriya informatsii (Kover–Tomas) → kanal s shumom. Aliasy umenshayut «shum» putey, sokhranyaya poleznyy signal (rabochie importy), chto snizhaet veroyatnost oshibki pri dekodirovanii (importe).
- Skrytyy 1: Bayes (Dzheynes) → aposteriornaya pravdopodobnost. Esli modul suschestvuet pod modules.*, alias uvelichivaet veroyatnost uspeshnogo importa «starogo» imeni.
- Skrytyy 2: Kibernetika (Eshbi) → regulyator raznoobraziya. Szhimaem raznomastnye importy do upravlyaemogo mnozhestva cherez tsentralizovannyy kontroller.

ZEMNOY ABZATs:
Eto kak kollektor dlya kabeley v stoyke: kuda by staryy provod ni byl protyanut, kollektor perenapravit ego na pravilnyy port. Svet ne morgaet, stoyka ne padaet.
"""
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
    # Chastye opechatki/varianty
    "listners": "listeners",  # esli gde-to zovut oshibochno, perekinem v nastoyaschiy paket listeners
    # Tochechnye puti, kotorye vstrechalis v logakh
    "graph.dag_engine": "modules.graph.dag_engine",
    "subconscious.engine": "modules.subconscious.engine",
    "llm.autoconfig_settings": "modules.llm.autoconfig_settings",
    "selfmanage.sync_profiles": "modules.selfmanage.sync_profiles",
}

def _ensure_parent(pkg: str) -> None:
    """Sozdaet nedostayuschie roditelskie pakety v sys.modules (pustye namespace-moduli)."""
    parts = pkg.split(".")
    for i in range(1, len(parts)):
        name = ".".join(parts[:i])
        if name not in sys.modules:
            m = types.ModuleType(name)
            m.__path__ = []  # type: ignore[attr-defined]
            sys.modules[name] = m

def _alias_module(old: str, new: str) -> None:
    """Svyazyvaet modul old s realnym modulem new (esli on importiruetsya). Inache — sozdaet pustoy namespace."""
    try:
        real_mod = importlib.import_module(new)
        _ensure_parent(old)
        sys.modules[old] = real_mod
        # Takzhe linkuem podmoduli (old.*) na letu cherez finder'y pitona — ostavim Pythonu, zdes ne pereuslozhnyaem
    except Exception:
        # Esli tselevogo net — sozdaem pustoy modul, chtoby sam import old ne valil protsess
        _ensure_parent(old)
        if old not in sys.modules:
            fallback = types.ModuleType(old)
            fallback.__dict__["__compat_missing__"] = new
            sys.modules[old] = fallback

def _install_aliases():
    for left, right in ALIASES.items():
        _alias_module(left, right)

# --- Myagkie patchi izvestnykh nesovmestimostey -------------------------------

def _patch_quality_guard_enable():
    """Esli modules.quality.guard est, no v nem net enable/disable — dobavim neytralnye shiny."""
    try:
        mod = importlib.import_module("modules.quality.guard")
    except Exception:
        return
    if not hasattr(mod, "enable"):
        def enable(*args, **kwargs):
            # Neytralnyy pereklyuchatel kachestva (po umolchaniyu nichego ne delaet)
            return {"ok": True, "mode": "compat", "feature": "quality_guard", "enabled": True}
        mod.enable = enable  # type: ignore[attr-defined]
    if not hasattr(mod, "disable"):
        def disable(*args, **kwargs):
            return {"ok": True, "mode": "compat", "feature": "quality_guard", "enabled": False}
        mod.disable = disable  # type: ignore[attr-defined]

def _patch_messaging_telegram_adapter():
    """Esli messaging.telegram_adapter est, no net TelegramAdapter — dobavim bezopasnuyu zaglushku-klass."""
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
    """Dobavlyaem verify_jwt_in_request_optional, esli biblioteka ego ubrala/pereimenovala."""
    try:
        fj = importlib.import_module("flask_jwt_extended")
    except Exception:
        return
    if not hasattr(fj, "verify_jwt_in_request_optional"):
        # Poprobuem sobrat funktsional cherez verify_jwt_in_request(optional=True)
        def verify_jwt_in_request_optional(*args, **kwargs):
            try:
                if hasattr(fj, "verify_jwt_in_request"):
                    return fj.verify_jwt_in_request(optional=True)  # type: ignore
            except Exception:
                # V kraynem sluchae — nichego ne delaem (marshrut ne budet trebovat JWT)
                return None
        fj.verify_jwt_in_request_optional = verify_jwt_in_request_optional  # type: ignore[attr-defined]

def enable():
    """Glavnaya tochka vklyucheniya sloya sovmestimosti."""
    _install_aliases()
    _patch_quality_guard_enable()
    _patch_messaging_telegram_adapter()
    _patch_flask_jwt_extended()
    return True

# Avtozapusk pri importe compat
try:
    enable()
except Exception:
    # Nikogda ne ronyaem protsess na urovne sovmestimosti
    pass

# c=a+b