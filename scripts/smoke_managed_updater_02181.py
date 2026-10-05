from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def wait_health(base: str, version: str, timeout: float = 30) -> dict:
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        try:
            r = httpx.get(base + "/health", timeout=2)
            if r.status_code == 200:
                body = r.json()
                if body.get("version") == version:
                    return body
                last = body
        except Exception as exc:
            last = exc
        time.sleep(0.35)
    raise AssertionError(f"health never reached {version}: {last}")


def build_target(tmp: Path, version: str, broken: bool = False) -> Path:
    src = tmp / f"src-{version}"
    (src / "app").mkdir(parents=True)
    shutil.copytree(ROOT / "app", src / "app", dirs_exist_ok=True)
    shutil.copy2(ROOT / "requirements.txt", src / "requirements.txt")
    (src / "app" / "__init__.py").write_text(f'__version__ = "{version}"\n', "utf-8")
    if broken:
        with (src / "app" / "main.py").open("a", encoding="utf-8") as fh:
            fh.write("\nraise RuntimeError('intentional updater rollback smoke failure')\n")
    out = tmp / f"update-{version}.zip"
    subprocess.run([
        sys.executable, str(ROOT / "scripts" / "build_update_package.py"),
        "--source", str(src),
        "--minimum-source-version", "0.2.18.1",
        "--target-version", version,
        "--health-timeout-seconds", "4" if broken else "20",
        "--output", str(out),
    ], check=True, stdout=subprocess.DEVNULL)
    return out


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="cocklebur_managed_updater_smoke_") as td:
        tmp = Path(td)
        data = tmp / "data"
        runtime = data / ".runtime"
        data.mkdir()
        target_ok = build_target(tmp, "0.2.18.2")
        target_bad = build_target(tmp, "0.2.18.3", broken=True)
        port = free_port()
        base = f"http://127.0.0.1:{port}"
        env = dict(os.environ)
        env.update({
            "POPUP_APP_MODE": "server",
            "POPUP_DATA_DIR": str(data),
            "POPUP_BASE_URL": base,
            "COCKLEBUR_BOOTSTRAP_KEY": "updater-smoke-bootstrap-key",
            "COCKLEBUR_BUNDLED_RUNTIME": str(ROOT),
            "COCKLEBUR_RUNTIME_DIR": str(runtime),
            "COCKLEBUR_INTERNAL_PORT": str(port),
        })
        proc = subprocess.Popen([sys.executable, str(ROOT / "bootstrap" / "supervisor.py")], env=env, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            first = wait_health(base, "0.2.18.1", 35)
            instance_id = first["instance_id"]
            client = httpx.Client(base_url=base, follow_redirects=True, timeout=20)
            r = client.post("/api/host/claim", json={"key": "updater-smoke-bootstrap-key", "display_name": "Smoke Host"})
            assert r.status_code == 200, r.text
            recovery = r.json()["host_recovery_code"]
            assert recovery

            with target_ok.open("rb") as fh:
                r = client.post("/api/update/stage", files={"file": (target_ok.name, fh, "application/zip")}, timeout=60)
            assert r.status_code == 200, r.text
            staged = r.json()
            assert staged["apply_supported"] is True
            r = client.post("/api/update/apply")
            assert r.status_code == 200, r.text
            second = wait_health(base, "0.2.18.2", 35)
            assert second["instance_id"] == instance_id
            assert second["host_claimed"] is True
            r = client.get("/api/host/status")
            assert r.status_code == 200 and r.json()["host"] is True, r.text

            with target_bad.open("rb") as fh:
                r = client.post("/api/update/stage", files={"file": (target_bad.name, fh, "application/zip")}, timeout=60)
            assert r.status_code == 200, r.text
            assert r.json()["apply_supported"] is True
            r = client.post("/api/update/apply")
            assert r.status_code == 200, r.text
            # The bad release must fail health and return to 0.2.18.2.
            rollback = wait_health(base, "0.2.18.2", 25)
            assert rollback["instance_id"] == instance_id
            deadline = time.monotonic() + 15
            state = None
            while time.monotonic() < deadline:
                try:
                    r = client.get("/api/update/status")
                    if r.status_code == 200:
                        state = (r.json().get("staged") or {}).get("state")
                        if state == "rolled_back":
                            break
                except Exception:
                    pass
                time.sleep(0.4)
            assert state == "rolled_back", state
            print("PASS — managed updater applies, restarts, preserves Host state, health-checks, and rolls back")
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                proc.kill(); proc.wait(timeout=3)
            if proc.returncode not in {0, -15}:
                out = proc.stdout.read() if proc.stdout else ""
                if out:
                    print(out)


if __name__ == "__main__":
    main()
