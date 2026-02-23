# -*- coding: utf-8 -*-
"""
tools/synergy_generate_schemas.py — generatsiya JSON-skhem modeley Synergy.

MOSTY:
- (Yavnyy) Serializuet Pydantic-skhemy v papku schemas/synergy/*.schema.json.
- (Skrytyy #1) Ne trebuet zapuschennogo prilozheniya; chistyy skript.
- (Skrytyy #2) Spisok modeley — odna tochka pravdy dlya eksporta.

ZEMNOY ABZATs:
Skhemy nuzhny CI i integratsiyam: validirovat vkhod/vykhod bez pinkov bekenda.

# c=a+b
"""
from __future__ import annotations
import json
import os
from modules.synergy.models import (
    Agent,
    Policy,
    Override,
    AssignmentRequest,
    AssignmentPlan,
    AssignmentStep,
    Outcome,
    TelemetryEvent,
    Capability,
    Role,
    Risk,
)

OUT_DIR = "schemas/synergy"

def ensure_dir(path: str):
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)

def dump_schema(model, name: str):
    schema = model.schema()  # pydantic v1
    with open(os.path.join(OUT_DIR, f"{name}.schema.json"), "w", encoding="utf-8") as f:
        json.dump(schema, f, ensure_ascii=False, indent=2)

def main():
    ensure_dir(OUT_DIR)
    dump_schema(Agent, "Agent")
    dump_schema(Policy, "Policy")
    dump_schema(Override, "Override")
    dump_schema(AssignmentRequest, "AssignmentRequest")
    dump_schema(AssignmentPlan, "AssignmentPlan")
    dump_schema(AssignmentStep, "AssignmentStep")
    dump_schema(Outcome, "Outcome")
    dump_schema(TelemetryEvent, "TelemetryEvent")
    dump_schema(Capability, "Capability")
    dump_schema(Role, "Role")
    dump_schema(Risk, "Risk")
    print(f"✓ Schemas written to {OUT_DIR}/")

if __name__ == "__main__":
    main()