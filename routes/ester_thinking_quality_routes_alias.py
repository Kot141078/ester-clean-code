"""Ester thinking quality HTTP alias + quality guard.

Route:
  POST /ester/thinking/quality_once
    {
      "goal": "...",          # tsel kaskada
      "priority": "high",     # optsionalno
      "trace": true           # pozhelanie trassirovki (ispolzuetsya kaskadom/adapterami)
    }

Povedenie (rezhim A/B):
- Always:
    * add volevoy impuls (volition_priority_adapter or volition_registry),
    * vyzyvaet always_thinker.consume_once(),
    * izvlekaet kaskad (result or ves dict),
    * analyze kachestvo cherez modules.ester.thinking_quality.analyze_cascade.
- ESTER_THINK_QONCE_AB = "A" (defolt):
    * only diagnostics of quality, without interference in the course of thinking.
- ESTER_THINK_QONCE_AB = "B":
    * if human_like=False or quarrel below the threshold, automatically starts
      glubokiy lokalnyy kaskad cherez modules.thinking.cascade_closed.run_cascade(goal),
      povtorno analyzet kachestvo i, esli ono luchshe i human_like=True,
      prikladyvaet resultat kak escalation.
    * iskhodnyy otvet always_thinker ostaetsya netronutym (prozrachnaya nadstroyka).

Zemnoy abzats:
Kak v inzhenernoy sisteme upravleniya: snachala izmeryaem signal (kachestvo kaskada),
zatem po determinirovannomu pravilu vklyuchaem bolee tochnyy kontur, esli pervyy
prokhod slishkom grubyy. Bez skrytykh pobochnykh effektov i s ponyatnym flagom rezhima."""

from __future__ import annotations

import os
from flask import Blueprint, jsonify, request
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

_BP_NAME = "ester_thinking_quality_alias"
_ROUTE = "/ester/thinking/quality_once"


def _get_env_ab(name: str, default: str = "A") -> str:
    v = os.environ.get(name, default)
    if not isinstance(v, str):
        return default
    v = v.strip().upper()
    return "B" if v == "B" else "A"


def create_blueprint() -> Blueprint:
    bp = Blueprint(_BP_NAME, __name__)

    @bp.route(_ROUTE, methods=["POST"])
    def ester_thinking_quality_once():
        data = request.get_json(silent=True) or {}

        goal = (data.get("goal") or "quality http human_like probe").strip()
        if not goal:
            goal = "quality http human_like probe"

        priority = (data.get("priority") or "high").strip() or "high"
        trace_wanted = bool(data.get("trace", True))

        # Imports with soft falsification - we don’t break the environment if something is missing.
        try:
            from modules.thinking import volition_priority_adapter as vpa
        except Exception:
            vpa = None

        try:
            from modules.thinking import volition_registry as vreg
        except Exception:
            vreg = None

        try:
            from modules import always_thinker
        except Exception as e:
            return jsonify({
                "ok": False,
                "error": f"always_thinker import failed: {e.__class__.__name__}: {e}",
            }), 500

        try:
            from modules.ester import thinking_quality as tq
        except Exception as e:
            return jsonify({
                "ok": False,
                "error": f"thinking_quality import failed: {e.__class__.__name__}: {e}",
            }), 500

        # 1) Volevoy impuls / prioritizatsiya
        if vpa is not None:
            try:
                vpa.enqueue(goal, {"priority": priority})
            except Exception:
                if vreg is not None:
                    try:
                        vreg.add_impulse({"goal": goal})
                    except Exception:
                        pass
        elif vreg is not None:
            try:
                vreg.add_impulse({"goal": goal})
            except Exception:
                pass

        # 2) Odin shag always_thinker
        try:
            raw = always_thinker.consume_once()
        except Exception as e:
            return jsonify({
                "ok": False,
                "error": f"always_thinker.consume_once failed: {e.__class__.__name__}: {e}",
            }), 500

        # 3) We take out the cascade for analysis (simple / multi / profile-vased)
        cascade = raw.get("result") or raw

        # 4) Bazovyy analiz human_like-kachestva
        try:
            quality = tq.analyze_cascade(cascade)
        except Exception as e:
            quality = {
                "ok": False,
                "error": f"analyze_cascade failed: {e.__class__.__name__}: {e}",
            }

        escalation = None
        ab_mode = _get_env_ab("ESTER_THINK_QONCE_AB", "A")

        # 5) Optional auto-escalation (mode B)
        if (
            ab_mode == "B"
            and isinstance(quality, dict)
            and quality.get("ok")
            and not quality.get("human_like", False)
        ):
            try:
                from modules.thinking import cascade_closed as cc
            except Exception:
                cc = None

            if cc is not None:
                try:
                    deep = cc.run_cascade(goal)
                    deep_q = tq.analyze_cascade(deep)

                    if (
                        isinstance(deep_q, dict)
                        and deep_q.get("ok")
                        and deep_q.get("human_like")
                        and float(deep_q.get("score", 0.0)) >= float(quality.get("score", 0.0))
                    ):
                        escalation = {
                            "ok": True,
                            "used": "cascade_closed.run_cascade",
                            "cascade": deep,
                            "quality": deep_q,
                        }
                        # We update the visible quality metrics: it shows that Esther has gone deeper
                        quality = {
                            "ok": True,
                            "meta": deep_q.get("meta", {}),
                            "score": deep_q.get("score"),
                            "human_like": True,
                            "reason": "auto-escalated via deep cascade (ESTER_THINK_QONCE_AB=B); "
                                      + (deep_q.get("reason") or "kaskad dostig tselevykh kriteriev"),
                        }
                    else:
                        escalation = {
                            "ok": False,
                            "reason": "deep cascade did not improve quality or not human_like",
                            "quality": deep_q,
                        }
                except Exception as e:
                    escalation = {
                        "ok": False,
                        "error": f"deep cascade failed: {e.__class__.__name__}: {e}",
                    }

        used = [
            "volition_priority_adapter.enqueue" if vpa is not None else "volition_registry.add_impulse",
            "always_thinker.consume_once",
            "thinking_quality.analyze_cascade",
        ]
        if escalation and escalation.get("ok"):
            used.append("cascade_closed.run_cascade (auto-escalation)")

        resp = {
            "ok": True,
            "goal": goal,
            "used": used,
            "raw": raw,
            "quality": quality,
        }
        if escalation is not None:
            resp["escalation"] = escalation

        return jsonify(resp)

    return bp


def register(app) -> None:
    """AUTO-REG entry dlya faylovogo avtoloadera marshrutov.

    Nothing ne menyaem v suschestvuyuschem app.py:
    esli /ester/thinking/quality_once uzhe est - vykhodim tikho."""
    try:
        bp = create_blueprint()
    except Exception as e:
        print("[ester-thinking-quality/routes] blueprint create failed:", e)
        return

    existing = {rule.rule for rule in app.url_map.iter_rules()}
    if _ROUTE in existing:
        return

    try:
        app.register_blueprint(bp)
        print(f"[ester-thinking-quality/routes] registered {_ROUTE}")
    except Exception as e:
        print("[ester-thinking-quality/routes] register failed:", e)