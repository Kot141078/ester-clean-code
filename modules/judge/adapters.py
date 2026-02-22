# -*- coding: utf-8 -*-
"""Adapters for evaluating tasks under a given config."""
from __future__ import annotations
from typing import Dict, Any, List
import json, subprocess, urllib.request, urllib.error
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

class BaseAdapter:
    def evaluate(self, config: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
        raise RuntimeError(
            "adapter_not_configured: provide DummyAdapter, ExternalProcessAdapter, or HTTPAdapter"
        )

class DummyAdapter(BaseAdapter):
    def evaluate(self, config: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
        t = float(config.get("llm", {}).get("temperature", 0.5))
        rag_k = int(config.get("rag", {}).get("k", 4))
        jmode = str(config.get("judge", {}).get("mode", "majority"))
        utility = 1.0 - abs(t - 0.3)
        accuracy = 0.6 + 0.1 * (rag_k >= 3) + (0.1 if jmode == "consensus" else 0.0)
        time_sec = 0.3 + 0.05 * rag_k
        err_rate = 0.05 + abs(t - 0.3) * 0.2
        return {
            "utility": max(0.0, min(1.0, utility)),
            "accuracy": max(0.0, min(1.0, accuracy)),
            "time_sec": max(0.01, time_sec),
            "err_rate": max(0.0, min(1.0, err_rate)),
            "tokens_prompt": 128,
            "tokens_gen": 256,
            "details": {"adapter": "dummy"}
        }

class ExternalProcessAdapter(BaseAdapter):
    def __init__(self, cmd: List[str]):
        self.cmd = cmd
    def evaluate(self, config: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
        payload = {"config": config, "task": task}
        p = subprocess.Popen(self.cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        out, err = p.communicate(json.dumps(payload))
        if p.returncode != 0:
            raise RuntimeError(f"External evaluator failed: rc={p.returncode} stderr={err[:1000]}")
        return json.loads(out)

class HTTPAdapter(BaseAdapter):
    def __init__(self, url: str, timeout: float = 30.0):
        self.url = url
        self.timeout = timeout
    def evaluate(self, config: Dict[str, Any], task: Dict[str, Any]) -> Dict[str, Any]:
        payload = json.dumps({"config": config, "task": task}).encode("utf-8")
        req = urllib.request.Request(self.url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as resp:
            body = resp.read().decode("utf-8")
        return json.loads(body)
