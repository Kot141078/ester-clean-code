from modules.memory.facade import memory_add, ESTER_MEM_FACADE


# === AUTOSHIM: added by tools/fix_no_entry_routes.py ===
# stub for computer_use_visual_anchor: no power supply/router/register_*_rutes yet
def register(app):
    return True

# === /AUTOSHIM ===