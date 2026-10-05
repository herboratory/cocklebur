# Cocklebur Server Managed Update Package 1.1

Cocklebur Server 0.2.18.1 adds a **managed runtime updater**. In the standard Docker image, the Cocklebur web process can validate and stage an update, then request a small PID-1 supervisor to apply it. The web process still receives no Docker socket, Kubernetes credential, root shell, or host-management permission.

## ZIP layout

```text
cocklebur-server-update.zip
├─ update-manifest.json
├─ checksums.json
└─ payload/
   ├─ requirements.txt
   └─ app/
      └─ ... Cocklebur runtime files ...
```

Example manifest:

```json
{
  "format": "cocklebur-server-update",
  "format_version": "1.1",
  "apply_mode": "managed-runtime-v1",
  "update_id": "SERVER-0.2.19",
  "minimum_source_version": "0.2.18.1",
  "target_version": "0.2.19",
  "restart_required": true,
  "health_timeout_seconds": 45,
  "data_migration": false
}
```

`checksums.json` maps every payload file to its SHA-256 digest. Unchecked or missing payload files are rejected.

## Apply lifecycle

A Host uses **Update center** to:

1. upload the update ZIP;
2. validate path safety, version compatibility and checksums;
3. create a pre-update data backup;
4. stage the package under `POPUP_DATA_DIR/.updates/`;
5. click **Apply update**.

The web process writes only a local apply request. The managed-runtime supervisor then independently re-checks the staged package, copies it to a new release slot under `POPUP_DATA_DIR/.runtime/`, atomically switches the active release, restarts Uvicorn, and verifies `/health` reports the target version.

If health verification fails, the supervisor switches back to the previous release and restarts it automatically. The pre-update data backup is preserved.

## Dependency boundary

Managed Runtime v1 deliberately does not install new Python dependencies. `requirements.txt` in the target package must match the active release exactly. An update that changes Python dependencies requires a new base container image/deployment. This keeps the in-app updater from becoming a general package installer.

## Data boundary

Application releases live under `.runtime/`; project data, Host state and project identities remain outside the release slot. The pre-update backup excludes updater staging/runtime directories and includes the actual Cocklebur data state.

## Trust boundary

Package 1.1 verifies SHA-256 integrity and path safety but does not yet include publisher-signature verification. Only an Instance Host should upload packages obtained from a trusted Cocklebur release source.

## Older package format 1.0

Format 1.0 packages may still be staged for inspection/backups, but they are not executable by the managed updater. Build new packages with format 1.1.
