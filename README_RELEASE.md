# Ester — Release Starter

Etot paket dobavlyaet minimalnyy konveyer relizov i publikatsiyu konteynera v GHCR.

## Soderzhimoe
- `.github/workflows/release.yml` — trigger po tegu `v*.*.*`, GH Release, push v GHCR, SBOM+podpis (opts.).
- `scripts/check_release_toolchain.sh` — proverka ustanovlennogo okruzheniya.
- `config/payment_links.env` — primer fayla dlya ssylok Stripe.
- `.env.example` — shablon lokalnykh peremennykh.

## Shagi
1. Skopiruy `.env.example` v `.env` i zapolni po instruktsii.
2. Zaday sekrety v repozitorii:
   - `GPG_PRIVATE_KEY` (opts.), `GPG_PASSPHRASE` (esli est),
   - `GPG_FINGERPRINT`,
   - `STRIPE_PAYMENT_LINK_MAIN`, `STRIPE_PAYMENT_LINK_PRO` (esli nuzhny v CI).
3. Sozday teg:
   ```bash
   git tag -a v0.1.0 -m "v0.1.0"
   git push origin v0.1.0
   ```
4. Prover vkladki **Actions** i **Packages**.
