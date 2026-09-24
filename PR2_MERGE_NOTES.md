# Cocklebur Server 0.2.17 — PR2 merge notes

This 0.2.17 feature package was implemented and regression-tested from the attached Cocklebur Server 0.2.15 source baseline. The deployment branch currently used by the server also contains the PR2 0.2.16 instance-auth/deployment work. Do **not** replace that branch wholesale with this package.

Use this package as the feature source and preserve the PR2 deployment/auth layer while merging the 0.2.17 changes.

## Keep from PR2 / 0.2.16

Keep the existing Docker/Kubernetes/Helm deployment files and the 0.2.16 instance-level authorization model, including:

- Host claim / Host recovery / Host sessions
- `instance_access(...)`
- delegated `Create projects` / `Import project packs` permissions
- `require_instance_permission(...)`
- Host != Project Owner semantics
- the existing deployment secrets, PVC/volume configuration, ingress and image workflow

Do not copy runtime `.env`, `/data`, instance secrets, Host recovery state, project data or browser credentials into the release source.

## Merge these 0.2.17 feature files/changes

The functional changes are concentrated in:

- `app/__init__.py` — version 0.2.17
- `app/config.py` — update-package size setting
- `app/models.py` — Note type + workspace import commit model
- `app/storage.py` — Note normalization, Card-create idempotency, Workspace Bundle helpers
- `app/main.py` — bundle/preflight/commit endpoints, idempotent Card POST, Update Center staging endpoints
- `app/static/app.js` — Note UI, safe Saving state, multi-import/bundle UI, Update Center UI
- `app/static/app.css` — three Card-type tabs on one row + New Project spacing
- `app/templates/index.html` — Export accessible / multi-import / Update Center controls
- `app/templates/project.html` — Note filter/copy
- `app/update_center.py` — new, data-safe update validation/staging/backup implementation
- `scripts/build_update_package.py` — new update-package builder
- `scripts/smoke_server_0217.py` — focused post-merge smoke test

Supporting format/release documentation is also included.

## Important PR2 integration rule: Import permission

The 0.2.15-based full source uses Host authorization for the new batch import endpoints. On the PR2 0.2.16 branch, preserve delegated Import capability by authorizing both new routes with the existing instance permission helper:

```python
require_instance_permission(request, "import")
```

This applies to:

```text
POST /api/projects/import/preflight
POST /api/projects/import/commit
```

The existing single-project import route should keep the same PR2 rule.

## Important PR2 integration rule: Update Center

Update Center is infrastructure-sensitive and should remain **Host-only**:

```text
GET    /api/update/status
POST   /api/update/stage
DELETE /api/update/staged
```

These routes should continue to call `require_host(request)` even on PR2. Delegated project Import permission must not grant update-package access.

## Workspace export permission

`GET /api/projects/export-bundle` must export only projects for which the current browser has a valid project identity. Host status alone must not grant project content access.

## Card create idempotency

Keep the 0.2.17 `X-Idempotency-Key` behavior on Card creation. The browser keeps one key for the lifetime of a New Card modal, disables Save while a request is active, and safely reuses the same key if the user retries after a timeout. The server returns the already-created Card instead of creating a duplicate.

## Note compatibility

Notes remain Cards with stable Card IDs:

```json
{"type": "note"}
```

No new project-pack major schema is introduced; project pack format stays `1.0`.

Note normalization:

- no task/event assignees or start/end/all-day fields
- lifecycle is `active` / `archived`
- Server still retains multiplayer `visibility`, `edit_access`, creator and activity metadata

## Update Center scope in 0.2.17

0.2.17 intentionally stops at:

```text
upload -> validate -> checksum/path-safety -> pre-update backup -> stage
```

It does **not** expose Docker socket, Kubernetes credentials, arbitrary shell execution, app-file replacement or self-restart to the Cocklebur web process. A narrowly privileged updater/apply service is a separate later phase.

Project/runtime data live outside the staged update payload and are never replaced by the update package.

## Post-merge checks

Run from repository root after merging into PR2:

```bash
python scripts/smoke_server_0217.py
python scripts/package_guard.py
```

Then on the deployed Server manually verify:

1. Host and delegated Create/Import permissions still behave as in 0.2.16.
2. Create a To-do and deliberately retry the same Card create idempotency key; only one Card exists.
3. Create/archive/restore a Note.
4. Export accessible projects as Workspace Bundle, preflight it, and import duplicates as new IDs.
5. Stage a signed-by-checksum test update package and confirm a pre-update backup is created; clear the stage and confirm the backup remains.
6. Existing project data and project-pack 1.0 export/import remain intact.
