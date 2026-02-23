import yaml
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

with open("proactive_rules.yaml", "r", encoding="utf-8") as f:
    data = yaml.safe_load(f)

print("YAML OK, keys:", list(data.keys()))