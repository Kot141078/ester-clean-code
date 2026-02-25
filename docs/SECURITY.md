# SECURITY - RVACH and protection of administrative zones

**What does this package provide**
- Roles **weaver / operator / admin** for е/admin/*е, optionally for е/export/*е and е/board/*е.
- Authentication modes: **Basic** (preferably through hashes) or **Token** (Bearer/YOH-Admin-Token).
- Built-in **rate limit** on protected paths.
- Vse — bez lomki suschestvuyuschikh routov (middleware).

## Connection
```python
from app_mount_all import mount_all
from security.mount_security import mount_security

mount_all(app)
mount_security(app)   # chitaet SECURITY_MODE i vklyuchaet RBAC

---

