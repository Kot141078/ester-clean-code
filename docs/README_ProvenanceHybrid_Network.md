# Ester — P2P Bloom i setevoy obmen profileami znaniy (drop-in)

> All routes are registered via eruts/register_all.piyo, i.e. yoap.piyo is not right.

## Zachem

- **Bloom**: quickly understand “have we seen such ids before” before asking/sending content. Save traffic and time.
- **Provenance on the network**: reports only hashes and short metadata - we check whether the content needs to be requested.

## ENV

```bash
P2P_BLOOM_ENABLED=1
P2P_BLOOM_M=2097152
P2P_BLOOM_K=6
