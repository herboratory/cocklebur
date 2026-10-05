# Updating Cocklebur Server

Cocklebur 0.2.18.1 introduces the managed-runtime updater used by the Host-only **Update center**.

## One-time bootstrap requirement

A server that is still running 0.2.17.2 or an earlier image does not contain the updater supervisor. It must be deployed **once** with the 0.2.18.1 (or newer) managed-updater image. No update ZIP can make an older running process execute an updater it does not contain.

Preserve the existing `.env` and `/data` volume during this one-time deployment.

After that bootstrap deployment, ordinary application updates that do not change Python dependencies can be applied from the web UI.

## Normal managed update

1. Sign in as Instance Host.
2. Open **Update center**.
3. Upload a format 1.1 Cocklebur Server Update ZIP.
4. Click **Validate & stage**.
5. Review target version and backup path.
6. Click **Apply update**.
7. Cocklebur restarts itself, checks `/health`, and reloads the page after the target version is healthy.

If the new application does not become healthy, Cocklebur automatically returns to the previous runtime release. The pre-update backup is kept.

## What the web app cannot do

The web process never receives Docker or Kubernetes administration credentials. It cannot replace containers, mount the Docker socket or execute arbitrary host commands. It can only ask the local Cocklebur supervisor to switch between validated runtime release slots in the persistent data volume.

## Updates that change Python dependencies

Managed Runtime v1 requires the target `requirements.txt` to exactly match the active release. A dependency-changing release needs a normal container/image deployment so the base Python environment can be rebuilt safely.

## Building an update package

```bash
python scripts/build_update_package.py \
  --source ./cocklebur-runtime \
  --minimum-source-version 0.2.18.1 \
  --target-version 0.2.19 \
  --output ./cocklebur-server-update-0.2.19.zip
```

The source directory must contain `app/` and `requirements.txt`. Only those runtime files are included in the package.
