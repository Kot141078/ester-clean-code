import os

from cryptography.hazmat.primitives.asymmetric import ed25519
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Puti iz tvoego zaprosa
SIGN_PRIVATE_KEY_PATH = "./secrets/ed25519.sk"
SIGN_PUBLIC_KEY_PATH = "./secrets/ed25519.pk"

# Sozdaem direktoriyu secrets/, esli ne suschestvuet
os.makedirs("secrets", exist_ok=True)

# Generiruem privatnyy klyuch Ed25519
private_key = ed25519.Ed25519PrivateKey.generate()

# Poluchaem publichnyy klyuch
public_key = private_key.public_key()

# Poluchaem raw-bayty: dlya privatnogo — seed (32 bayta), no dlya polnogo SK dobavlyaem public (standart 64 bayta)
seed = private_key.private_bytes_raw()  # 32 bayta seed
public_bytes = public_key.public_bytes_raw()  # 32 bayta public
full_private_bytes = seed + public_bytes  # 64 bayta dlya .sk

# Sokhranyaem privatnyy klyuch (64 bayta)
with open(SIGN_PRIVATE_KEY_PATH, "wb") as f:
    f.write(full_private_bytes)

# Sokhranyaem publichnyy klyuch (32 bayta)
with open(SIGN_PUBLIC_KEY_PATH, "wb") as f:
    f.write(public_bytes)

print(
    f"Klyuchi sgenerirovany i sokhraneny:\n- {SIGN_PRIVATE_KEY_PATH} (privatnyy, 64 bayta: seed + public, derzhi v sekrete!)\n- {SIGN_PUBLIC_KEY_PATH} (publichnyy, 32 bayta, mozhno delit)"
)