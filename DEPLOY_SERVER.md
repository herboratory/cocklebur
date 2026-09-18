# Cocklebur Server Deployment

## Requirements

- Docker Engine + Docker Compose plugin (recommended), or Python 3.12/3.13
- Persistent storage mounted at `/data`
- HTTPS for Internet-facing deployments
- Exactly **one application worker**

## 1. Docker Compose

```bash
cp .env.example .env
```

Local test:

```dotenv
POPUP_APP_MODE=server
POPUP_DATA_DIR=/data
POPUP_HOST_PORT=8000
POPUP_BASE_URL=http://127.0.0.1:8000
COCKLEBUR_BOOTSTRAP_KEY=replace-with-a-long-random-secret
```

Generate a key, for example:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Start:

```bash
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:8000/health
```

The Compose file binds to localhost by default. Put an HTTPS reverse proxy or tunnel in front for public use.

## 2. First Host claim

The deployment key is a **bootstrap credential**, not a permanent Host password.

1. Open the Projects page.
2. Click **Claim Host**.
3. Enter a Host display name and the bootstrap key.
4. Save the Host recovery code Cocklebur shows you.

After claim:

- the bootstrap key is no longer accepted for Host login;
- the Host browser keeps an HttpOnly Host session cookie;
- a new browser uses **Host recovery**;
- successful recovery rotates the Host recovery code while preserving existing Host sessions.

For compatibility, `COCKLEBUR_HOST_KEY` is accepted as an alias for `COCKLEBUR_BOOTSTRAP_KEY`.

If neither variable is set, Cocklebur still generates a bootstrap key in `/data/.host_key`; you can retrieve it with:

```bash
docker compose exec popup-workspace cat /data/.host_key
```

For production, explicitly setting `COCKLEBUR_BOOTSTRAP_KEY` is clearer.

## 3. Deployer and Host may be different people

The Infrastructure Admin / Deployer may create the VM/container and then securely hand the bootstrap key to the intended Cocklebur Host. Claiming Host does not make the deployer a Cocklebur app user.

However, anyone with root/admin control of the server or persistent volume can technically read, alter, back up, restore, or delete Cocklebur data. Application permissions do not override infrastructure control.

## 4. Delegated Create / Import

Host always has both instance capabilities:

- Create projects
- Import project packs

Host may open **Instance permissions** on the Projects page and grant either capability independently to an existing project identity. That person keeps their existing project role.

Examples:

- Member + Create = can create a new project and becomes Owner of that new project.
- Viewer + Import = can import a pack but remains Viewer in the original project.
- Owner without Create/Import = can administer their project but cannot create/import at instance level.

Delegated permission is tied to that existing project identity/browser credential. Removing that identity from the project removes the associated instance grant.

## 5. Host port vs public URL

`POPUP_HOST_PORT` controls the host-side Docker port. `POPUP_BASE_URL` controls absolute invite/recovery URLs.

For example:

```dotenv
POPUP_HOST_PORT=8003
POPUP_BASE_URL=https://cocklebur.example.org
```

After `.env` changes:

```bash
docker compose up -d --force-recreate
```

## 6. Clean reset

**This deletes all Cocklebur data in the named Docker volume:**

```bash
docker compose down -v --remove-orphans
```

Ordinary restart — keep the volume:

```bash
docker compose down
docker compose up -d
```

A fresh/empty `/data` means a new Cocklebur instance and therefore a new Host claim.

## 7. Direct Python deployment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export POPUP_APP_MODE=server
export POPUP_DATA_DIR=/srv/cocklebur-data
export POPUP_BASE_URL=https://workspace.example.org
export COCKLEBUR_BOOTSTRAP_KEY='replace-with-a-long-random-secret'
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --proxy-headers
```

Do not increase the worker count for this file-backed release.

## 8. Troubleshooting

```bash
docker compose logs --tail=200 popup-workspace
```
