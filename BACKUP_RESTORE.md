# Cocklebur Server Backup & Restore

## Preferred project backup

Use **Export current state** inside each important project. Export briefly locks the project snapshot, then creates a ZIP containing machine-readable state, human-readable text, checksums, and original files.

## Infrastructure backup

The Docker named volume may also be backed up at the infrastructure level. For the strongest consistency, either stop the Cocklebur container first or use project Export for application-level snapshots.

Normal Docker restart:

```bash
docker compose down
docker compose up -d
```

This preserves the named volume.

Do **not** run `docker compose down -v` unless you intentionally want to delete the Cocklebur volume.

## Restore a project pack

1. Open Projects.
2. Obtain **Host access**.
3. Choose **Import pack**.
4. Select the exported ZIP.
5. Cocklebur validates paths, checksums, schema, and required data before installation.
6. The imported project becomes the canonical Server copy on this deployment.
7. The importing browser receives Owner access and a fresh Owner recovery code.

If the same project ID already exists on the instance, import is rejected by default rather than silently creating another writable copy.
