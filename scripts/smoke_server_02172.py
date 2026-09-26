from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import zipfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="cocklebur_02172_smoke_") as td:
        os.environ["POPUP_APP_MODE"] = "server"
        os.environ["POPUP_DATA_DIR"] = str(Path(td) / "data")
        os.environ["POPUP_BASE_URL"] = "http://testserver"
        os.environ["COCKLEBUR_BOOTSTRAP_KEY"] = "smoke-bootstrap-key"

        from fastapi.testclient import TestClient
        from app.main import app, store

        c = TestClient(app, base_url="http://testserver")
        health = c.get("/health").json()
        assert health["version"] == "0.2.17.2"
        assert health["host_claimed"] is False

        # First Host claim: bootstrap works exactly once and returns durable recovery.
        claim = c.post("/api/host/claim", json={"key": "smoke-bootstrap-key", "display_name": "Smoke Host"})
        assert claim.status_code == 200, claim.text
        recovery1 = claim.json()["host_recovery_code"]
        assert recovery1 and c.get("/api/instance/access").json()["host"] is True
        assert c.get("/health").json()["host_claimed"] is True

        # Bootstrap must not behave like a permanent password after claim.
        fresh = TestClient(app, base_url="http://testserver")
        again = fresh.post("/api/host/claim", json={"key": "smoke-bootstrap-key", "display_name": "Other"})
        assert again.status_code == 409, again.text

        # Clearing cookies/new browser: current recovery code restores Host and rotates.
        recovered = fresh.post("/api/host/recover", json={"code": recovery1.lower()})
        assert recovered.status_code == 200, recovered.text
        recovery2 = recovered.json()["host_recovery_code"]
        assert recovery2 != recovery1
        assert fresh.get("/api/instance/access").json()["host"] is True

        stale = TestClient(app, base_url="http://testserver")
        assert stale.post("/api/host/recover", json={"code": recovery1}).status_code == 403
        recovered2 = stale.post("/api/host/recover", json={"code": recovery2})
        assert recovered2.status_code == 200, recovered2.text

        # Existing 0.2.17 functionality stays present.
        project = stale.post("/api/projects", json={"name": "Smoke", "mode": "server", "owner_name": "Smoke Owner", "timezone": "UTC"}).json()
        pid = project["id"]
        payload = {"type": "note", "title": "Smoke note", "content": "hello", "tags": ["smoke"]}
        headers = {"X-Idempotency-Key": "smoke-idempotency"}
        first = stale.post(f"/api/projects/{pid}/cards", json=payload, headers=headers)
        second = stale.post(f"/api/projects/{pid}/cards", json=payload, headers=headers)
        assert first.status_code == 200 and second.status_code == 200
        assert first.json()["id"] == second.json()["id"]
        assert second.headers.get("x-idempotency-replayed") == "true"

        bundle = stale.get("/api/projects/export-bundle")
        assert bundle.status_code == 200
        with zipfile.ZipFile(io.BytesIO(bundle.content)) as zf:
            assert "bundle-manifest.json" in zf.namelist()
            assert "checksums.json" in zf.namelist()

        preflight = stale.post("/api/projects/import/preflight", files={"files": ("workspace.zip", bundle.content, "application/zip")})
        assert preflight.status_code == 200
        batch = preflight.json()
        assert batch["entries"] and batch["entries"][0]["status"] == "Duplicate ID"
        committed = stale.post("/api/projects/import/commit", json={"batch_id": batch["batch_id"], "duplicate_policy": "new_id"})
        assert committed.status_code == 200

        data = b"smoke update"
        digest = hashlib.sha256(data).hexdigest()
        manifest = {"format": "cocklebur-server-update", "format_version": "1.0", "target_version": "0.2.18", "minimum_source_version": "0.2.17", "restart_required": True}
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("update-manifest.json", json.dumps(manifest))
            zf.writestr("checksums.json", json.dumps({"payload/smoke.txt": digest}))
            zf.writestr("payload/smoke.txt", data)
        staged = stale.post("/api/update/stage", files={"file": ("update.zip", buf.getvalue(), "application/zip")})
        assert staged.status_code == 200, staged.text
        assert Path(staged.json()["backup_path"]).exists()

        # Break-glass reset: projects/grants stay, Host claim is cleared.
        backup = store.reset_host_claim()
        assert backup and backup.exists()
        assert store.host_claimed() is False
        assert store.get_project(pid)["id"] == pid
        reclaim = TestClient(app, base_url="http://testserver").post(
            "/api/host/claim", json={"key": "smoke-bootstrap-key", "display_name": "Reclaimed Host"}
        )
        assert reclaim.status_code == 200, reclaim.text

    print("PASS — Cocklebur Server 0.2.17.2 smoke")


if __name__ == "__main__":
    main()
