from __future__ import annotations

import os
import tempfile
from pathlib import Path
import sys
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def token_from_url(url: str) -> str:
    return parse_qs(urlparse(url).query)["token"][0]


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="cocklebur_0218_smoke_") as td:
        os.environ["POPUP_APP_MODE"] = "server"
        os.environ["POPUP_DATA_DIR"] = str(Path(td) / "data")
        os.environ["POPUP_BASE_URL"] = "http://testserver"
        os.environ["COCKLEBUR_BOOTSTRAP_KEY"] = "smoke-bootstrap-key"

        from fastapi.testclient import TestClient
        from app.main import app, store

        host = TestClient(app, base_url="http://testserver", headers={"user-agent": "Mozilla/5.0 Macintosh Safari/605.1.15"})
        health = host.get("/health").json()
        assert health["version"] == "0.2.18.1"
        assert health["host_claimed"] is False

        # Claim Host on device A.
        claim = host.post("/api/host/claim", json={"key": "smoke-bootstrap-key", "display_name": "Smoke Host"})
        assert claim.status_code == 200, claim.text
        host_recovery = claim.json()["host_recovery_code"]
        host_devices = host.get("/api/host/devices").json()["devices"]
        assert len(host_devices) == 1 and host_devices[0]["current"] is True

        # Normal Host multi-device linking must not use/rotate recovery.
        link = host.post("/api/host/device-link")
        assert link.status_code == 200, link.text
        host_link = link.json()
        assert host_link["one_time"] is True
        assert host.get(host_link["qr_url"]).status_code == 200

        phone_host = TestClient(app, base_url="http://testserver", headers={"user-agent": "Mozilla/5.0 (iPhone) Version/18.0 Mobile Safari/604.1"})
        get_link = phone_host.get(urlparse(host_link["device_link_url"]).path + "?" + urlparse(host_link["device_link_url"]).query)
        assert get_link.status_code == 200 and "Same identity, another browser" in get_link.text
        exchange = phone_host.post("/host-device-link", data={"token": token_from_url(host_link["device_link_url"]), "device_label": "My iPhone"}, follow_redirects=False)
        assert exchange.status_code == 303, exchange.text
        assert phone_host.get("/api/instance/access").json()["host"] is True
        assert host.get("/api/instance/access").json()["host"] is True
        # Link is one-time.
        replay = TestClient(app, base_url="http://testserver").post("/host-device-link", data={"token": token_from_url(host_link["device_link_url"]), "device_label": "Replay"}, follow_redirects=False)
        assert replay.status_code == 403
        # Recovery code is unchanged by Add device.
        recover_elsewhere = TestClient(app, base_url="http://testserver").post("/api/host/recover", json={"code": host_recovery})
        assert recover_elsewhere.status_code == 200, recover_elsewhere.text

        # Project owner created on host browser.
        project = host.post("/api/projects", json={"name": "Multi-device", "mode": "server", "owner_name": "Owner", "timezone": "UTC"})
        assert project.status_code == 200, project.text
        pdata = project.json(); pid = pdata["id"]
        owner_me = host.get(f"/api/projects/{pid}/me").json()
        owner_id = owner_me["id"]
        owner_devices = host.get(f"/api/projects/{pid}/me/devices").json()["devices"]
        assert len(owner_devices) == 1 and owner_devices[0]["current"] is True

        # Link same owner identity to phone. Member count must not change.
        before_people = host.get(f"/api/projects/{pid}/people").json()
        plink = host.post(f"/api/projects/{pid}/me/device-link")
        assert plink.status_code == 200, plink.text
        plinkj = plink.json()
        assert host.get(plinkj["qr_url"]).status_code == 200

        owner_phone = TestClient(app, base_url="http://testserver", headers={"user-agent": "Mozilla/5.0 (iPhone) CriOS/120 Mobile"})
        target_url = urlparse(plinkj["device_link_url"])
        preview = owner_phone.get(target_url.path + "?" + target_url.query)
        assert preview.status_code == 200 and "same project identity" in preview.text.lower()
        linked = owner_phone.post(target_url.path, data={"token": token_from_url(plinkj["device_link_url"]), "device_label": "Owner phone"}, follow_redirects=False)
        assert linked.status_code == 303, linked.text
        phone_me = owner_phone.get(f"/api/projects/{pid}/me")
        assert phone_me.status_code == 200
        assert phone_me.json()["id"] == owner_id and phone_me.json()["role"] == "owner"
        after_people = host.get(f"/api/projects/{pid}/people").json()
        assert len(after_people) == len(before_people) == 1
        assert host.get(f"/api/projects/{pid}/me").json()["id"] == owner_id

        # Existing device remains valid; both sessions appear and non-current one can be revoked.
        devices = host.get(f"/api/projects/{pid}/me/devices").json()["devices"]
        assert len(devices) == 2
        phone_device = next(d for d in devices if not d["current"])
        revoked = host.delete(f"/api/projects/{pid}/me/devices/{phone_device['id']}")
        assert revoked.status_code == 200, revoked.text
        assert owner_phone.get(f"/api/projects/{pid}/me").status_code == 401
        assert host.get(f"/api/projects/{pid}/me").status_code == 200

        # Current device cannot revoke itself.
        current = host.get(f"/api/projects/{pid}/me/devices").json()["devices"][0]
        assert current["current"] is True
        assert host.delete(f"/api/projects/{pid}/me/devices/{current['id']}").status_code == 400

        # No hidden 8-session cap: add ten more browser sessions to the same person.
        linked_clients = []
        for i in range(10):
            generated = host.post(f"/api/projects/{pid}/me/device-link").json()
            other = TestClient(app, base_url="http://testserver")
            parsed = urlparse(generated["device_link_url"])
            result = other.post(parsed.path, data={"token": token_from_url(generated["device_link_url"]), "device_label": f"Browser {i+1}"}, follow_redirects=False)
            assert result.status_code == 303, result.text
            assert other.get(f"/api/projects/{pid}/me").json()["id"] == owner_id
            linked_clients.append(other)
        devices = host.get(f"/api/projects/{pid}/me/devices").json()["devices"]
        assert len(devices) == 11, len(devices)
        assert host.get(f"/api/projects/{pid}/me").status_code == 200

        # A normal Invite still creates a new person, proving Invite != Add device.
        invite = host.post(f"/api/projects/{pid}/invite/regenerate", json={"pin": None}).json()
        member = TestClient(app, base_url="http://testserver")
        joined = member.post(f"/api/projects/{pid}/join", json={"display_name": "Member", "token": invite["token"], "pin": None})
        assert joined.status_code == 200, joined.text
        member_id = joined.json()["person"]["id"]
        assert member_id != owner_id
        assert len(host.get(f"/api/projects/{pid}/people").json()) == 2

        # Member can self-link another device without Owner intervention.
        mlink = member.post(f"/api/projects/{pid}/me/device-link").json()
        member_phone = TestClient(app, base_url="http://testserver")
        mparsed = urlparse(mlink["device_link_url"])
        assert member_phone.post(mparsed.path, data={"token": token_from_url(mlink["device_link_url"]), "device_label": "Member phone"}, follow_redirects=False).status_code == 303
        assert member_phone.get(f"/api/projects/{pid}/me").json()["id"] == member_id
        assert len(host.get(f"/api/projects/{pid}/people").json()) == 2

        # Legacy 0.2.17.x access_hash-only sessions remain valid and manageable.
        people_path = store._path(pid, "people.json")
        people = store._read_json(people_path, [])
        owner = next(p for p in people if p["id"] == owner_id)
        owner.pop("device_sessions", None)
        store._atomic_write_json(people_path, people)
        legacy = host.get(f"/api/projects/{pid}/me/devices").json()["devices"]
        assert any(d["legacy"] for d in legacy)
        assert host.get(f"/api/projects/{pid}/me").status_code == 200


        # Exported portable packs must not carry live browser/device credentials.
        exported_path, _meta = store.export_project(pid)
        import zipfile, json
        with zipfile.ZipFile(exported_path) as zf:
            exported_people = json.loads(zf.read("data/people.json"))
        for person in exported_people:
            assert person.get("access_hashes") == []
            assert person.get("device_sessions") == []
            assert "device_link_hash" not in person
            assert "owner_recovery_hash" not in person

        # Host recovery/break-glass still work after multi-device changes.
        latest_recovery = recover_elsewhere.json()["host_recovery_code"]
        fresh = TestClient(app, base_url="http://testserver")
        assert fresh.post("/api/host/recover", json={"code": latest_recovery}).status_code == 200
        backup = store.reset_host_claim()
        assert backup and backup.exists()
        assert store.host_claimed() is False
        reclaim = TestClient(app, base_url="http://testserver").post("/api/host/claim", json={"key": "smoke-bootstrap-key", "display_name": "Reclaimed"})
        assert reclaim.status_code == 200

    print("PASS — Cocklebur Server 0.2.18.1 multi-device smoke")


if __name__ == "__main__":
    main()
