# Updating Cocklebur Server

Project data lives in the persistent server data volume, outside the application image.

## Before updating

1. Export every important active project.
2. Back up the Docker volume / server data directory.
3. Record the current Cocklebur version and keep the previous release package until the update is verified.

## Docker update

Replace the application source with the new release, preserve your `.env`, then:

```bash
docker compose down
docker compose build --pull
docker compose up -d
curl http://127.0.0.1:${POPUP_HOST_PORT:-8000}/health
```

`docker compose down` does not remove the named volume.

**Do not use `docker compose down -v` during a normal update.** `-v` deletes the Cocklebur volume.

## Direct Python deployment

Replace application code, reinstall `requirements.txt`, then restart the single server worker.

## Project-pack compatibility

Project packs declare `format_version`. This release uses format `1.0`; older compatible packs are normalized during import where required.


## Server 0.2.17 Update Center staging

A Host may open **Update center** on the Projects page and upload a Cocklebur Server Update ZIP. 0.2.17 validates paths/checksums/version compatibility, creates a pre-update data backup, and stages the package under `POPUP_DATA_DIR/.updates/`.

This is intentionally a **staging boundary only**. The web process does not receive Docker socket access, Kubernetes credentials, arbitrary shell access, or self-restart authority. Application replacement/restart/health-check/rollback remains the job of a separately privileged deployer/updater.

See `UPDATE_PACKAGE_FORMAT.md`. A helper is included:

```bash
python scripts/build_update_package.py \
  --source ./release-payload \
  --minimum-source-version 0.2.17 \
  --target-version 0.2.18 \
  --output ./cocklebur-server-update-0.2.18.zip
```
