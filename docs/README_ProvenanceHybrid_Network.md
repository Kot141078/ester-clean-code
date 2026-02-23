# Ester — P2P Bloom i setevoy obmen profileami znaniy (drop-in)

> Vse marshruty registriruyutsya cherez `routes/register_all.py`, t.e. `app.py` ne pravim.

## Zachem

- **Bloom**: bystro ponyat, «videli li my uzhe takie id», prezhde chem prosit/slat soderzhimoe. Ekonomit trafik i vremya.
- **Provenance v seti**: soobschaem lish kheshi i korotkie metadannye — sveryaemsya, nuzhno li zaprashivat kontent.

## ENV

```bash
P2P_BLOOM_ENABLED=1
P2P_BLOOM_M=2097152
P2P_BLOOM_K=6
