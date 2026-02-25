import os

from cryptography.hazmat.primitives.asymmetric import ed25519
from modules.memory.facade import memory_add, ESTER_MEM_FACADE

# Paths from your request
SIGN_PRIVATE_KEY_PATH = "./secrets/ed25519.sk"
SIGN_PUBLIC_KEY_PATH = "./secrets/ed25519.pk"

# Create the secrets/ directory if it does not exist
os.makedirs("secrets", exist_ok=True)

# Generate private key D25519
private_key = ed25519.Ed25519PrivateKey.generate()

# Getting the public key
public_key = private_key.public_key()

# We get equal bytes: for private - seed (32 bytes), but for full social network we add public (standard 64 bytes)
seed = private_key.private_bytes_raw()  # 32 bayta seed
public_bytes = public_key.public_bytes_raw()  # 32 bayta public
full_private_bytes = seed + public_bytes  # 64 bytes for .sk

# Save the private key (64 bytes)
with open(SIGN_PRIVATE_KEY_PATH, "wb") as f:
    f.write(full_private_bytes)

# Save the public key (32 bytes)
with open(SIGN_PUBLIC_KEY_PATH, "wb") as f:
    f.write(public_bytes)

print(
    f"Keys are generated and saved:\n- ZZF0Z (private, 64 bytes: seed + public, keep it secret!)\n- ZZF1ZZ (public, 32 bytes, can be divided)"
)