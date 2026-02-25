# -*- coding: utf-8 -*-
"""security/provenance.py - sovmestimost s istoricheskim putem importa.
Polnyy funktsional nakhoditsya v modules/security/provenance.py.
This modul reeksportiruet publichnye funktsii i struktury, chtoby ne lomat starye importy."""

from modules.security.provenance import (  # type: ignore
    _load_registries,
    forward_to_bus,
    record_event,
    verify_event,
)

__all__ = [
    "_load_registries",
    "forward_to_bus",
    "record_event",
    "verify_event",
]
