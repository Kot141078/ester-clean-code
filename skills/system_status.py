import platform
import datetime
from typing import Dict, Any
from .base import EsterSkill
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

class SystemStatusSkill(EsterSkill):
    @property
    def name(self) -> str:
        return "check_system_status"

    @property
    def description(self) -> str:
        return "Returns current server time, OS version and basic telemetry."

    @property
    def parameters(self) -> Dict[str, str]:
        return {}

    def execute(self, **kwargs) -> Dict[str, Any]:
        return {
            "status": "success",
            "timestamp": datetime.datetime.now().isoformat(),
            "os": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
            "processor": platform.processor()
        }