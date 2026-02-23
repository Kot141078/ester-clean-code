# -*- coding: utf-8 -*-
from __future__ import annotations
import os
from typing import Optional
from modules.memory.facade import memory_add, ESTER_MEM_FACADE
__all__ = ["ENV_OPENAI_BASE","ENV_OPENAI_KEY","ENV_LMSTUDIO_BASE","ENV_JUDGE_MODE","ENV_JUDGE_MODEL","get_env","get_env_bool","get_active_provider_hint"]
ENV_OPENAI_BASE="OPENAI_API_BASE"; ENV_OPENAI_KEY="OPENAI_API_KEY"; ENV_LMSTUDIO_BASE="LMSTUDIO_BASE"; ENV_JUDGE_MODE="JUDGE_MODE"; ENV_JUDGE_MODEL="JUDGE_MODEL"
def get_env(n:str,d:Optional[str]=None)->Optional[str]: return os.environ.get(n,d)
def get_env_bool(n:str,default:bool=False)->bool:
    v=os.environ.get(n); 
    if v is None: return default
    v=v.strip().lower(); return v in ("1","true","yes","on")
def get_active_provider_hint()->str:
    sel=os.environ.get("ESTER_PROVIDER_SELECTED")
    if sel: return sel
    if os.environ.get(ENV_OPENAI_BASE) and os.environ.get(ENV_OPENAI_KEY): return "openai"
    if os.environ.get(ENV_OPENAI_BASE) or os.environ.get(ENV_LMSTUDIO_BASE): return "lmstudio"
    return "local"