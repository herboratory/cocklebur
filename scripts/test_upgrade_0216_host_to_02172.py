from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="cocklebur_0216_upgrade_") as td:
        data_dir = Path(td) / "data"
        data_dir.mkdir()
        os.environ["POPUP_APP_MODE"] = "server"
        os.environ["POPUP_DATA_DIR"] = str(data_dir)
        os.environ["POPUP_BASE_URL"] = "http://testserver"
        os.environ["COCKLEBUR_BOOTSTRAP_KEY"] = "bootstrap-from-0216"

        from app.security import token_hash

        old_recovery = "ABCDE-FGHJK-MNPQR-STUVW"
        old_access = "old-browser-session-token"
        auth = {
            "version": 1,
            "host": {
                "display_name": "0.2.16 Host",
                "claimed_at": "2026-09-18T00:00:00Z",
                "access_hashes": [token_hash(old_access)],
                "recovery_hash": token_hash(old_recovery),
                "recovery_updated_at": "2026-09-18T00:00:00Z",
            },
            "grants": [],
        }
        (data_dir / ".instance_auth.json").write_text(json.dumps(auth), encoding="utf-8")

        from fastapi.testclient import TestClient
        from app.main import app

        c = TestClient(app, base_url="http://testserver")
        health = c.get("/health").json()
        assert health["version"] == "0.2.17.2"
        assert health["host_claimed"] is True

        # Simulate cache/cookie clearing: no Host cookie, but the 0.2.16 recovery code remains valid.
        access = c.get("/api/instance/access").json()
        assert access["host"] is False and access["host_claimed"] is True
        recovered = c.post("/api/host/recover", json={"code": old_recovery})
        assert recovered.status_code == 200, recovered.text
        assert recovered.json()["host_recovery_code"] != old_recovery
        assert c.get("/api/instance/access").json()["host"] is True

        # Once claimed, the old bootstrap is intentionally not a login password.
        other = TestClient(app, base_url="http://testserver")
        assert other.post("/api/host/claim", json={"key": "bootstrap-from-0216", "display_name": "Host"}).status_code == 409

    print("PASS — 0.2.16 Host state upgrades to 0.2.17.2 and recovery survives cleared cookies")


if __name__ == "__main__":
    main()
