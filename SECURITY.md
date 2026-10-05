# Cocklebur Server Security Notes

## Access model

- Server project membership uses project-scoped browser credentials stored in `HttpOnly` cookies.
- Instance-level **Host access** controls Create / Import and is separate from project Owner / Member / Viewer roles.
- Invite tokens should be treated as secrets until exchanged for membership.
- Recovery links are one-time. Opening the link only shows confirmation; the token is consumed on confirmed recovery.
- Recovery restores the existing identity and does **not** revoke other valid sessions.
- Owner break-glass recovery codes rotate after successful use.
- Cookies are marked `Secure` when `POPUP_BASE_URL` uses HTTPS.
- Optional project PINs add friction but do not replace HTTPS or proper access controls.

## Deployment

For Internet-facing use:

- terminate HTTPS in front of Cocklebur;
- keep the application port bound to localhost/private infrastructure;
- run exactly **one application worker**;
- protect the host machine and persistent data volume;
- keep `COCKLEBUR_BOOTSTRAP_KEY`, Host recovery codes, `POPUP_SECRET_KEY`, invite/recovery links, and recovery codes private.

The JSON/JSONL storage layer uses filesystem locking and assumes a single application writer process. The provided Docker command uses one worker.

## Data handling

Self-hosted mode does not require a central project-data service operated by the software author. Project content stays in storage selected by the deployer. This does not remove privacy, security, retention, consent, or other legal obligations that may apply to a deployment.

## Reporting a security issue

Do not publish live exploits, credentials, or private project data. Report security issues privately to the project maintainer with reproducible steps where possible.

## Multi-device access (0.2.18)

- Planned additional-device access uses short-lived, single-use bearer links; it does not reuse recovery credentials.
- Device-link tokens are stored only as hashes and expire after 10 minutes.
- Generating a new device link replaces the previous outstanding link for that identity.
- Existing browser sessions remain valid when another device is linked.
- Non-current device sessions can be revoked individually.
- Portable Project Packs strip browser-session hashes, device-session metadata, pending device-link state, and Owner recovery hashes before packaging.
