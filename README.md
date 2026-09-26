# Cocklebur Server — MVP

**Release:** `0.2.17.2`  
**Project pack format:** `1.0`

Cocklebur Server is a lightweight, self-hosted project workspace for bounded projects: keep one canonical live copy, collaborate in a browser, then export the whole project as a portable ZIP when the work is done.

This archive is the **Server distribution**. It intentionally does not include the Local/pywebview/Tauri desktop build tooling or old acceptance/hotfix documents.

Cocklebur is intended for **personal, academic/research, teaching/educational, and non-commercial community use**. Commercial use is not granted; see `LICENSE`.

## Core model

- One canonical server copy per active project.
- File-backed storage: JSON / JSONL plus original uploaded files.
- No CRDT, offline multi-master sync, or silent conflict merge.
- Mutable entities use versions; stale writes return HTTP `409` instead of silently overwriting newer data.
- Export creates a consistent snapshot and includes machine-readable data, human-readable text, and original files.
- Server mode must run with **one application worker**.

## Quick start with Docker

```bash
cp .env.example .env
```

For a local test, the defaults may remain:

```dotenv
POPUP_APP_MODE=server
POPUP_DATA_DIR=/data
POPUP_HOST_PORT=8000
POPUP_BASE_URL=http://127.0.0.1:8000
```

For a stable deployment, set a long random one-time Host bootstrap key:

```dotenv
COCKLEBUR_BOOTSTRAP_KEY=replace-with-a-long-random-secret
```

Then start Cocklebur:

```bash
docker compose up -d --build
curl http://127.0.0.1:8000/health
```

Open `http://127.0.0.1:8000` for a local test. For Internet-facing use, keep the app bound to localhost and put HTTPS in front of it through a reverse proxy or tunnel. See `DEPLOY_SERVER.md`.

## Server access model

Cocklebur separates **instance-level Host access** from **project roles**:

- **Host** — may create or import projects on this Cocklebur instance.
- **Owner** — administers one project, invitations, roles, recovery, export/close/delete.
- **Member** — normal project collaboration.
- **Viewer** — read-only project access, except they may update their own display name.

A project role does not automatically grant Host access.

## Main features

### Projects
- Create/import projects through Host access.
- Active / closing / archived lifecycle.
- Optional expected end date.
- Export/import portable project packs.

### Cards
- To-do and Event cards.
- Pending / In Progress / Done / Archived status.
- Markdown content, tags, assignees, checklist items, dates, and `.ics` download for dated Events.
- **Visibility:** `Everyone` or `Only me`.
- **Edit access:** shared or creator-only.
- Assignees describe responsibility; they do not grant or restrict access.
- Delete is creator-only for both To-do and Event cards.
- Human-readable audit history records who changed content, status, schedule, and checklist items.

### Announcements, Discussion, Files
- Project announcements.
- Channels, titled threads, replies, and channel visibility by role/person.
- File upload/download with metadata, size/quota limits, SHA-256 digest, and optional Card links.

### Recovery
- Owners can generate one-time recovery links for existing collaborators.
- Opening a recovery link first shows a confirmation page; the token is consumed only when recovery is confirmed.
- Recovery restores the existing identity and **does not revoke other valid browser sessions**.
- Owners also have a break-glass recovery code. Successful Owner recovery rotates that code.

## Data and privacy

Self-hosted Cocklebur does not require a central project-data service operated by the software author. Project data lives in the storage controlled by the deployer. This is a technical architecture statement, not a waiver of privacy, security, or legal responsibilities.

For Internet-facing use:

- use HTTPS;
- keep one app worker;
- do not expose the raw Docker port publicly;
- back up the persistent data volume;
- protect the Host bootstrap key, Host recovery code, invite links, recovery links, and Owner recovery codes.

See `SECURITY.md`.

## Documentation

- `DEPLOY_SERVER.md` — deployment, clean reset, tunnels, and Host access
- `USER_GUIDE.md` / `USER_GUIDE_zh-Hant.md` — day-to-day use
- `BACKUP_RESTORE.md` — backup and restore
- `UPDATE.md` — safe updates
- `EXPORT_FORMAT.md` — portable project-pack format
- `SECURITY.md` — security model
- `RELEASE.md` — release metadata and limitations
- `CHANGELOG.md` — project history
- `LICENSE` — license terms

## Release validation

A lightweight source-package guard is included:

```bash
python scripts/package_guard.py
```

It checks required server-release files, rejects runtime secrets/project data/caches, and validates Python/JavaScript syntax when the relevant tools are available.


## Server 0.2.17.2

Adds Workspace Bundle export/import, Note Cards, retry-safe Card creation, New Project spacing polish, and Host-only data-safe Update Center staging. Host access uses a single explicit Bootstrap Key for first claim, browser Host sessions for normal use, and rotating Host recovery codes for recovery. Project Pack format remains 1.0.
