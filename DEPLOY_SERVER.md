# Cocklebur Server Deployment

## Requirements

- Docker Engine + Docker Compose plugin (recommended), or Python 3.12/3.13
- Persistent storage
- HTTPS for Internet-facing deployments
- Exactly **one application worker**

## 1. Docker Compose — localhost test

```bash
cp .env.example .env
```

Default local test:

```dotenv
POPUP_APP_MODE=server
POPUP_DATA_DIR=/data
POPUP_HOST_PORT=8000
POPUP_BASE_URL=http://127.0.0.1:8000
```

Generate a Host key, for example:

```bash
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

Put it in `.env`:

```dotenv
COCKLEBUR_HOST_KEY=replace-with-your-random-value
```

Start:

```bash
docker compose up -d --build
docker compose ps
curl http://127.0.0.1:8000/health
```

Open `http://127.0.0.1:8000` and use **Host access** with the Host key before Create / Import becomes available.

## 2. Host port vs public URL

These are separate settings:

```dotenv
POPUP_HOST_PORT=8000
POPUP_BASE_URL=http://127.0.0.1:8000
```

If you intentionally want localhost port 8003, change both:

```dotenv
POPUP_HOST_PORT=8003
POPUP_BASE_URL=http://127.0.0.1:8003
```

The container still listens on port 8000 internally.

After `.env` changes:

```bash
docker compose up -d --force-recreate
```

A rebuild is only required when application/dependency files changed.

## 3. Internet access through a tunnel / reverse proxy

The provided Compose file binds Cocklebur to `127.0.0.1`, not a public interface. Point your HTTPS proxy/tunnel at the local port.

Example with ngrok:

```bash
ngrok http 8000
```

If ngrok gives:

```text
https://example.ngrok-free.app
```

set:

```dotenv
POPUP_HOST_PORT=8000
POPUP_BASE_URL=https://example.ngrok-free.app
```

then:

```bash
docker compose up -d --force-recreate
```

Invite / QR / recovery URLs are generated from `POPUP_BASE_URL`.

For a permanent deployment, use your normal HTTPS reverse proxy or Cloudflare Tunnel and set `POPUP_BASE_URL` to the final public HTTPS origin.

## 4. Clean-room reset

**Warning: this intentionally deletes the Cocklebur Docker volume and all server project data in it. Export anything important first.**

From the directory containing `docker-compose.yml`:

```bash
docker compose down -v --remove-orphans
```

Optional inspection:

```bash
docker compose ps -a
docker volume ls
```

Then rebuild cleanly:

```bash
docker compose build --no-cache
docker compose up -d
docker compose ps
curl http://127.0.0.1:8000/health
```

For an ordinary restart, **do not use `-v`**:

```bash
docker compose down
docker compose up -d
```

The named volume is retained.

## 5. Server Host access

Host access is instance-level and separate from project Owner / Member / Viewer roles.

Recommended stable configuration:

```dotenv
COCKLEBUR_HOST_KEY=replace-with-a-long-random-secret
```

If omitted, Cocklebur generates a persistent key in `/data/.host_key`. With Docker you can read it using:

```bash
docker compose exec popup-workspace cat /data/.host_key
```

Do not share the Host key with normal project collaborators.

## 6. Direct Python deployment

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export POPUP_APP_MODE=server
export POPUP_DATA_DIR=/srv/cocklebur-data
export POPUP_BASE_URL=https://workspace.example.org
export COCKLEBUR_HOST_KEY='replace-with-a-long-random-secret'
uvicorn app.main:app --host 127.0.0.1 --port 8000 --workers 1 --proxy-headers
```

Do not increase the worker count for this file-backed MVP.

## 7. Importing an older project pack

Older format-1.0 packs are normalized for current permission/visibility metadata during import. On successful Server import, the importing browser receives Owner access to the imported project and a fresh Owner recovery code.

If the same project ID already exists on the instance, import is rejected rather than silently creating another writable copy.

## 8. Logs and troubleshooting

```bash
docker compose logs --tail=200 popup-workspace
```

Follow logs live:

```bash
docker compose logs -f popup-workspace
```

`Ctrl+C` exits the log viewer; it does not stop the container.
