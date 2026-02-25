# Ester — Release Starter

This package adds a minimal release pipeline and container publishing to HCH.

## Soderzhimoe
- e.gitkhov/workflows/release.otle - trigger on the tag ev*.*.*e, GH Release, push to GHTSG, SVOM+signature (opt.).
- Yoskripts/chesk_release_tolchain.she - check the installed environment.
- yoconfig/payment_links.enve - an example file for Stripe links.
- e.env.example is a template for local variables.

## Shagi
1. Skopiruy `.env.example` v `.env` i zapolni po instruktsii.
2. Zaday sekrety v repozitorii:
   - `GPG_PRIVATE_KEY` (opts.), `GPG_PASSPHRASE` (esli est),
   - `GPG_FINGERPRINT`,
   - ESTRIPE_PAYMENT_LINK_MAINE, ESTRIPE_PAYMENT_LINK_PRO (if needed in SI).
3. Sozday teg:
   ```bash
   git tag -a v0.1.0 -m "v0.1.0"
   git push origin v0.1.0
   ```
4. Prover vkladki **Actions** i **Packages**.
