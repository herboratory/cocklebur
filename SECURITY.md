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
- keep `COCKLEBUR_HOST_KEY`, `POPUP_SECRET_KEY`, invite/recovery links, and recovery codes private.

The JSON/JSONL storage layer uses filesystem locking and assumes a single application writer process. The provided Docker command uses one worker.

## Data handling

Self-hosted mode does not require a central project-data service operated by the software author. Project content stays in storage selected by the deployer. This does not remove privacy, security, retention, consent, or other legal obligations that may apply to a deployment.

## Reporting a security issue

Do not publish live exploits, credentials, or private project data. Report security issues privately to the project maintainer with reproducible steps where possible.
