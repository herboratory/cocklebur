# Cocklebur Server

**Release:** `0.2.16`  
**Project pack format:** `1.0`

Cocklebur Server is a lightweight, self-hosted project workspace for bounded projects: keep one canonical live copy, collaborate in a browser, then export the whole project as a portable ZIP when the work is done.

This archive is the **Server distribution**. It intentionally does not include desktop build tooling.

Cocklebur is made available for non-commercial use under the included license.

## Core model

- One canonical server copy per active project.
- File-backed storage: JSON / JSONL plus original uploaded files.
- No CRDT, offline multi-master sync, or silent conflict merge.
- Mutable entities use versions; stale writes return HTTP `409`.
- Export includes machine-readable data, human-readable text, and original files.
- Server mode must run with **one application worker**.

## Quick start with Docker

```bash
cp .env.example .env
```

For a local test:

```dotenv
POPUP_APP_MODE=server
POPUP_DATA_DIR=/data
POPUP_HOST_PORT=8000
POPUP_BASE_URL=http://127.0.0.1:8000
COCKLEBUR_BOOTSTRAP_KEY=replace-with-a-long-random-secret
```

`COCKLEBUR_HOST_KEY` is still accepted as a compatibility alias for the bootstrap key.

Then:

```bash
docker compose up -d --build
curl http://127.0.0.1:8000/health
```

Open `http://127.0.0.1:8000`. For Internet-facing use, keep the raw app port private and put HTTPS in front of it through your own reverse proxy or tunnel.

## Access model

Cocklebur separates infrastructure administration, instance administration, and project roles.

- **Infrastructure Admin / Deployer** — controls the machine, Docker, storage, backups, and network. This is outside Cocklebur's app roles.
- **Host** — application-level administrator for one Cocklebur instance.
- **Owner** — administers one specific project.
- **Member** — normal project collaboration.
- **Viewer** — read-only project access except for their own display name.

A person can also receive either or both of these **instance permissions** without becoming Host:

- **Create projects** — may create a new project and becomes Owner of that new project.
- **Import project packs** — may import a project pack and receives Owner access to the imported project.

Project Owner / Member / Viewer roles do not automatically grant Create or Import.

### Host bootstrap and recovery

`COCKLEBUR_BOOTSTRAP_KEY` is a one-time bootstrap credential. The intended Host uses **Claim Host** once. Cocklebur then creates application-level Host state inside the persistent data volume and shows a Host recovery code.

After claim, the bootstrap key is **not accepted as a standing Host password**. A new browser uses the current Host recovery code; successful recovery preserves existing Host sessions and rotates the recovery code.

The underlying infrastructure administrator still controls the server/storage and therefore remains technically capable of accessing or destroying self-hosted data. Cocklebur app permissions do not claim to restrict server root/admin access.

## Main features

- Projects with optional expected end dates
- Dashboard and announcements
- To-do and Event Cards
- Checklists, tags, assignees, visibility and edit-access controls
- Discussion channels with titled threads
- Project files
- Owner / Member / Viewer project roles
- Invitation and recovery flows
- Instance Create / Import delegation
- Portable project export / import

## Data and privacy

Self-hosted Cocklebur does not require a central Cocklebur project-data service operated by Herboratory. Project data lives in storage controlled by the deployment administrator.

For Internet-facing use:

- use HTTPS;
- keep one app worker;
- do not expose the raw Docker port directly;
- back up the persistent data volume;
- protect bootstrap/recovery credentials, invite links, and Owner recovery codes.

See `SECURITY.md` and `DEPLOY_SERVER.md`.
