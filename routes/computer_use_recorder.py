from modules.memory.facade import memory_add, ESTER_MEM_FACADE


# === AUTOSHIM: added by tools/fix_no_entry_routes.py ===
# zaglushka dlya computer_use_recorder: poka net bp/router/register_*_routes
def register(app):
    return True

# === /AUTOSHIM ===