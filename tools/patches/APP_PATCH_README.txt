# V app.py srazu posle _load_env_from_file() dobavte:

try:
    # Safe patch for vector/search + store/search
    from modules.memory import vector_store_safe_adapter as _ester_vector_store_safe  # noqa: F401
except Exception:
    _ester_vector_store_safe = None  # noqa: F401

# Dalee idet ostalnoy kod app.py
