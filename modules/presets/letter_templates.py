# -*- coding: utf-8 -*-
"""
modules/presets/letter_templates.py — Gotovye presety pisem/soobscheniy dlya Ester.

MOSTY:
- (Yavnyy) Privyazka preseta k audience+intent → chelovekochitaemaya sborka teksta po facts.
- (Skrytyy #1) Edinyy dvizhok renderinga iz persona_style_ext (pochta) i persona_style (messendzhery).
- (Skrytyy #2) Konservativnaya de-«kantselyarizatsiya» i validatsiya faktov (minimum obyazatelnykh poley).

ZEMNOY ABZATs:
Presety uskoryayut povsednevnuyu rabotu: «bank — status perevoda», «advokat — peredacha spravok»,
«gosorgan — zapis na priem», «medik — perenos vizita», «investor — KPI-apdeyt» i t.p.

# c=a+b
"""
from __future__ import annotations
from typing import Dict, Any, Callable

from modules.persona_style_ext import render_email
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

PresetFunc = Callable[[Dict[str, Any]], str]

def _require(facts: Dict[str, Any], keys: list[str]) -> None:
    missing = [k for k in keys if not str(facts.get(k) or "").strip()]
    if missing:
        raise ValueError("missing_facts:" + ",".join(missing))

# --- BANK ---
def bank_transfer_status(facts: Dict[str, Any]) -> str:
    _require(facts, ["date", "amount", "reference"])
    account = facts.get("account", "—")
    body = (
        f"Proshu podtverdit status perevoda {facts['reference']} na summu {facts['amount']} "
        f"ot {facts['date']}. Nomer scheta: {account}."
    )
    return render_email("bank", "letter", body)

def bank_statement_request(facts: Dict[str, Any]) -> str:
    _require(facts, ["period"])
    body = f"Proshu predostavit vypisku po schetu za period: {facts['period']}."
    return render_email("bank", "request", body)

# --- LAWYER ---
def lawyer_documents_submit(facts: Dict[str, Any]) -> str:
    _require(facts, ["case_no", "docs"])
    body = (
        f"Peredayu dokumenty po delu {facts['case_no']}: {facts['docs']}. "
        f"Proshu podtverdit poluchenie i soobschit o sleduyuschikh shagakh."
    )
    return render_email("lawyer", "letter", body)

def lawyer_hearing_reschedule(facts: Dict[str, Any]) -> str:
    _require(facts, ["old_time", "new_time", "date"])
    body = (
        f"Proshu perenesti zasedanie {facts['date']} s {facts['old_time']} na {facts['new_time']}. "
        f"Gotov predostavit podtverzhdayuschie dokumenty pri neobkhodimosti."
    )
    return render_email("lawyer", "request", body)

# --- GOV ---
def gov_appointment_request(facts: Dict[str, Any]) -> str:
    _require(facts, ["subject"])
    when = facts.get("when")
    body = f"Proshu naznachit priem po voprosu: {facts['subject']}." + (f" Predpochtitelnoe vremya: {when}." if when else "")
    return render_email("gov", "request", body)

# --- MEDIC ---
def medic_visit_reschedule(facts: Dict[str, Any]) -> str:
    _require(facts, ["date_old", "date_new"])
    reason = facts.get("reason")
    body = f"Proshu perenesti vizit s {facts['date_old']} na {facts['date_new']}." + (f" Prichina: {reason}." if reason else "")
    return render_email("medic", "reminder", body)

# --- ENGINEER ---
def engineer_ticket_update(facts: Dict[str, Any]) -> str:
    _require(facts, ["ticket", "status"])
    note = facts.get("note")
    body = f"Status zadachi {facts['ticket']}: {facts['status']}." + (f" Detali: {note}." if note else "")
    return render_email("engineer", "update", body)

# --- TEACHER ---
def teacher_absence_notice(facts: Dict[str, Any]) -> str:
    _require(facts, ["date"])
    reason = facts.get("reason", "semeynye obstoyatelstva")
    body = f"Soobschayu ob otsutstvii {facts['date']}: {reason}. Proshu vyslat zadaniya dlya samostoyatelnoy raboty."
    return render_email("teacher", "letter", body)

# --- INVESTOR ---
def investor_kpi_update(facts: Dict[str, Any]) -> str:
    _require(facts, ["period", "mrr", "growth"])
    next_call = facts.get("next_call")
    body = (
        f"KPI za {facts['period']}: MRR {facts['mrr']}, rost {facts['growth']}."
        + (f" Predlagayu sozvon {next_call}." if next_call else "")
    )
    return render_email("investor", "update", body)

# --- FRIEND / STUDENT / BUSINESS ---
def friend_meetup(facts: Dict[str, Any]) -> str:
    _require(facts, ["time", "place"])
    body = f"Vstretimsya v {facts['time']} u {facts['place']}. Esli chto — napishi."
    return render_email("friend", "update", body)

def student_homework_request(facts: Dict[str, Any]) -> str:
    _require(facts, ["subject"])
    body = f"Mozhesh poyasnit po teme «{facts['subject']}»? Chto zadali k sleduyuschemu zanyatiyu?"
    return render_email("student", "request", body)

def business_meeting_confirm(facts: Dict[str, Any]) -> str:
    _require(facts, ["date", "time", "place"])
    body = f"Podtverzhdayu vstrechu {facts['date']} v {facts['time']} ({facts['place']}). Do vstrechi."
    return render_email("business", "update", body)

PRESETS: dict[str, PresetFunc] = {
    # bank
    "bank.transfer_status": bank_transfer_status,
    "bank.statement_request": bank_statement_request,
    # lawyer
    "lawyer.documents_submit": lawyer_documents_submit,
    "lawyer.hearing_reschedule": lawyer_hearing_reschedule,
    # gov
    "gov.appointment_request": gov_appointment_request,
    # medic
    "medic.visit_reschedule": medic_visit_reschedule,
    # engineer
    "engineer.ticket_update": engineer_ticket_update,
    # teacher
    "teacher.absence_notice": teacher_absence_notice,
    # investor
    "investor.kpi_update": investor_kpi_update,
    # friend / student / business
    "friend.meetup": friend_meetup,
    "student.homework_request": student_homework_request,
    "business.meeting_confirm": business_meeting_confirm,
}