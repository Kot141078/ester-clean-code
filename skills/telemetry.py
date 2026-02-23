import psutil
import logging
# Popytka importa NVML dlya Nvidia
try:
    import pynvml
    HAS_NVIDIA = True
except ImportError:
    HAS_NVIDIA = False

from .base import EsterSkill
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

logger = logging.getLogger("Skill.Telemetry")

class HardwareSenseSkill(EsterSkill):
    @property
    def name(self) -> str:
        return "check_hardware_stats"

    @property
    def description(self) -> str:
        return "Returns internal system telemetry: CPU load, RAM usage, and GPU (VRAM/Temp) status."

    def execute(self, **kwargs):
        stats = {}
        try:
            # Basic OS Stats
            mem = psutil.virtual_memory()
            stats['ram_total_gb'] = round(mem.total / (1024**3), 2)
            stats['ram_used_gb'] = round(mem.used / (1024**3), 2)
            stats['ram_percent'] = mem.percent
            stats['cpu_percent'] = psutil.cpu_percent(interval=None)

            # GPU Stats (Nvidia)
            if HAS_NVIDIA:
                try:
                    pynvml.nvmlInit()
                    device_count = pynvml.nvmlDeviceGetCount()
                    gpu_list = []
                    for i in range(device_count):
                        handle = pynvml.nvmlDeviceGetHandleByIndex(i)
                        name = pynvml.nvmlDeviceGetName(handle)
                        if isinstance(name, bytes): name = name.decode('utf-8')
                        
                        mem_info = pynvml.nvmlDeviceGetMemoryInfo(handle)
                        temp = pynvml.nvmlDeviceGetTemperature(handle, pynvml.NVML_TEMPERATURE_GPU)
                        
                        gpu_list.append({
                            "id": i,
                            "name": name,
                            "vram_total_mb": mem_info.total // 1024**2,
                            "vram_free_mb": mem_info.free // 1024**2,
                            "temp_c": temp
                        })
                    stats['gpus'] = gpu_list
                    pynvml.nvmlShutdown()
                except Exception as nv_err:
                    stats['gpu_error'] = str(nv_err)
            else:
                stats['gpu_status'] = "No NVML driver found or pynvml not installed."

            return {"status": "success", "telemetry": stats}

        except Exception as e:
            logger.error(f"Telemetry failure: {e}")
            return {"status": "error", "message": str(e)}