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
    with tempfile.TemporaryDirectory(prefix="cocklebur_0217_smoke_") as td:
        os.environ["POPUP_APP_MODE"] = "server"
        os.environ["POPUP_DATA_DIR"] = str(Path(td) / "data")
        os.environ["POPUP_BASE_URL"] = "http://testserver"
        os.environ["COCKLEBUR_HOST_KEY"] = "smoke-host-key"

        from fastapi.testclient import TestClient
        from app.main import app

        c = TestClient(app, base_url="http://testserver")
        assert c.get("/health").json()["version"] == "0.2.17"
        assert c.post("/api/host/login", json={"key": "smoke-host-key"}).status_code == 200
        project = c.post("/api/projects", json={"name": "Smoke", "mode": "server", "owner_name": "Smoke Owner", "timezone": "UTC"}).json()
        pid = project["id"]

        payload = {"type": "note", "title": "Smoke note", "content": "hello", "tags": ["smoke"]}
        headers = {"X-Idempotency-Key": "smoke-idempotency"}
        first = c.post(f"/api/projects/{pid}/cards", json=payload, headers=headers)
        second = c.post(f"/api/projects/{pid}/cards", json=payload, headers=headers)
        assert first.status_code == 200 and second.status_code == 200
        assert first.json()["id"] == second.json()["id"]
        assert second.headers.get("x-idempotency-replayed") == "true"

        bundle = c.get("/api/projects/export-bundle")
        assert bundle.status_code == 200
        with zipfile.ZipFile(io.BytesIO(bundle.content)) as zf:
            assert "bundle-manifest.json" in zf.namelist()
            assert "checksums.json" in zf.namelist()

        preflight = c.post("/api/projects/import/preflight", files={"files": ("workspace.zip", bundle.content, "application/zip")})
        assert preflight.status_code == 200
        batch = preflight.json()
        assert batch["entries"] and batch["entries"][0]["status"] == "Duplicate ID"
        committed = c.post("/api/projects/import/commit", json={"batch_id": batch["batch_id"], "duplicate_policy": "new_id"})
        assert committed.status_code == 200

        data = b"smoke update"
        digest = hashlib.sha256(data).hexdigest()
        manifest = {"format": "cocklebur-server-update", "format_version": "1.0", "target_version": "0.2.18", "minimum_source_version": "0.2.17", "restart_required": True}
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr("update-manifest.json", json.dumps(manifest))
            zf.writestr("checksums.json", json.dumps({"payload/smoke.txt": digest}))
            zf.writestr("payload/smoke.txt", data)
        staged = c.post("/api/update/stage", files={"file": ("update.zip", buf.getvalue(), "application/zip")})
        assert staged.status_code == 200
        assert Path(staged.json()["backup_path"]).exists()

    print("PASS — Cocklebur Server 0.2.17 smoke")


if __name__ == "__main__":
    main()
