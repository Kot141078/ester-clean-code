# SECURITY — RBAC i zaschita administrativnykh zon

**Chto daet etot paket**
- Roli **viewer / operator / admin** dlya `/admin/*`, optsionalno dlya `/export/*` i `/board/*`.
- Rezhimy autentifikatsii: **Basic** (luchshe — cherez kheshi) ili **Token** (Bearer/`X-Admin-Token`).
- Vstroennyy **rate limit** na zaschischennykh putyakh.
- Vse — bez lomki suschestvuyuschikh routov (middleware).

## Podklyuchenie
```python
from app_mount_all import mount_all
from security.mount_security import mount_security

mount_all(app)
mount_security(app)   # chitaet SECURITY_MODE i vklyuchaet RBAC

---

