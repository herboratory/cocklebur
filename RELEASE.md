# Cocklebur Server Release

- **Release ID:** SERVER-0.2.17-WORKSPACE-NOTE-UPDATE-STAGING
- **Version:** 0.2.17
- **Project pack format:** 1.0
- **Workspace Bundle format:** 1.0
- **Server Update staging format:** 1.0
- **Distribution:** Docker / self-hosted Server source package

## Included scope

- Workspace Bundle export for all Owner/Member projects accessible in the current browser.
- Multi-pack / Workspace Bundle import with preflight: Ready, Duplicate ID, Invalid pack, Incompatible version.
- Retry-safe Card creation using browser-side Save locking plus server-side idempotency keys.
- Third Card type: Note. Notes keep title/content/tags, project visibility/edit access, and Active/Archived lifecycle without task status/assignee/event fields.
- New Project modal spacing polish.
- Host-only Update Center foundation: upload, path/checksum validation, minimum/target version checks, pre-update data backup, and staging.
- Update Center intentionally does **not** replace application files, invoke Docker/Kubernetes, or restart the server. A separately privileged updater is required for apply/restart/rollback.

## Data compatibility

Project Pack `format_version` remains **1.0**. Note is stored as a normal Card JSON with `type=note`; no second project schema is introduced. Workspace Bundle is a container of ordinary Project Pack 1.0 ZIPs. Runtime idempotency metadata and update-staging metadata are not exported as project data.

## Update safety boundary

Project data stays under `POPUP_DATA_DIR`. Update packages are forbidden from containing `data/`, `.env`, instance secret/id files, Host credentials, or instance auth state. Staging creates a compressed data backup under `.update_backups/` before declaring an update staged. Checksums protect package integrity, but 0.2.17 does not yet implement publisher-signature verification.
