# Cocklebur Server Update Package 1.0

Cocklebur Server 0.2.17 can **validate, back up data, and stage** an update package from the Host-only Update Center. It deliberately cannot replace the running application or control Docker/Kubernetes.

## ZIP layout

```text
cocklebur-server-update.zip
├─ update-manifest.json
├─ checksums.json
├─ payload/
│  └─ ... application/update files ...
├─ migrations/              # optional, if a future release needs them
└─ RELEASE.md               # optional
```

`update-manifest.json` example:

```json
{
  "format": "cocklebur-server-update",
  "format_version": "1.0",
  "update_id": "SERVER-0.2.18",
  "minimum_source_version": "0.2.17",
  "target_version": "0.2.18",
  "restart_required": true
}
```

`checksums.json` is an object mapping **every payload file other than the two manifest files** to its SHA-256 digest. Unchecked extra files are rejected.

## Forbidden paths

Update packages may not contain runtime data or credentials, including:

- `data/`
- `.env`
- `.instance_secret`
- `.instance_id`
- `.host_key`
- `.instance_auth.json`
- `.git/` / `.github/`

## Staging behavior

After validation Cocklebur:

1. creates a pre-update data backup under `POPUP_DATA_DIR/.update_backups/`;
2. saves the original update ZIP under `POPUP_DATA_DIR/.updates/<stage_id>/`;
3. extracts a validated payload beside it;
4. records `stage.json` and exposes the stage in Update Center.

It does **not** modify application code, restart the process, mount the Docker socket, or call a Kubernetes API. A future privileged updater should revalidate the staged package, apply it, run health checks, and roll back on failure.

## Trust note

Version 1.0 verifies path safety and SHA-256 integrity. It does not yet verify a publisher signature. Only a trusted Host should upload packages from a trusted release channel.
