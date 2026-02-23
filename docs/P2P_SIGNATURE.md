# P2P Signature — edinyy zagolovok i formula

**Most (yavnyy):** (Dok ↔ Guard) — dokumentatsiya sovpadaet s realizatsiey `security/p2p_signature.py`.

**Skrytye mosty:**  
1) (CLI ↔ Dok) — `scripts/p2p_sign.py` pechataet korrektnye zagolovki.  
2) (Legacy ↔ New) — server prinimaet `X-P2P-Signature` i aliasy (`X-P2P-Auth`, `X-HMAC-Signature`) dlya obratnoy sovmestimosti.

**Zemnoy abzats:** odna skhema podpisi → menshe padeniy 401 i bystree diagnostika.

---

## Standartnyy format

Zagolovki:
