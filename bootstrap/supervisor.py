from __future__ import annotations

import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BASE_ROOT = Path(os.getenv("COCKLEBUR_BUNDLED_RUNTIME", "/opt/cocklebur/base")).resolve()
DATA_ROOT = Path(os.getenv("POPUP_DATA_DIR", "/data")).resolve()
RUNTIME_ROOT = Path(os.getenv("COCKLEBUR_RUNTIME_DIR", str(DATA_ROOT / ".runtime"))).resolve()
RELEASES_ROOT = RUNTIME_ROOT / "releases"
CONTROL_ROOT = RUNTIME_ROOT / "control"
CURRENT_LINK = RUNTIME_ROOT / "current"
STATE_PATH = RUNTIME_ROOT / "runtime-state.json"
APPLY_REQUEST = CONTROL_ROOT / "apply-request.json"
PORT = int(os.getenv("COCKLEBUR_INTERNAL_PORT", "8000"))
HEALTH_URL = f"http://127.0.0.1:{PORT}/health"
STOPPING = False
CHILD: subprocess.Popen[Any] | None = None


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def read_json(path: Path, default: Any = None) -> Any:
    try:
        return json.loads(path.read_text("utf-8"))
    except Exception:
        return default


def write_json_atomic(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", "utf-8")
    os.replace(tmp, path)



def version_tuple(value: str) -> tuple[int, ...]:
    import re
    nums = [int(x) for x in re.findall(r"\d+", value or "")[:4]]
    return tuple(nums or [0])

def bundled_version() -> str:
    ns: dict[str, Any] = {}
    exec((BASE_ROOT / "app" / "__init__.py").read_text("utf-8"), ns)
    return str(ns.get("__version__") or "0")


def release_version(root: Path) -> str:
    ns: dict[str, Any] = {}
    exec((root / "app" / "__init__.py").read_text("utf-8"), ns)
    return str(ns.get("__version__") or "0")


def atomic_switch_release(release: Path) -> None:
    tmp = RUNTIME_ROOT / ".current.next"
    tmp.unlink(missing_ok=True)
    tmp.symlink_to(release, target_is_directory=True)
    os.replace(tmp, CURRENT_LINK)


def initialize_runtime() -> None:
    RELEASES_ROOT.mkdir(parents=True, exist_ok=True)
    CONTROL_ROOT.mkdir(parents=True, exist_ok=True)
    bundled = bundled_version()
    if CURRENT_LINK.is_symlink() and CURRENT_LINK.resolve().is_dir():
        active = CURRENT_LINK.resolve()
        try:
            active_version = release_version(active)
        except Exception:
            active_version = "0"
        # A newly deployed base image is authoritative when it is newer than
        # the persisted runtime. This is how dependency-changing/image-level
        # upgrades intentionally move the runtime forward. If the persisted
        # runtime is newer (because it was updated in-app), keep it.
        if version_tuple(active_version) >= version_tuple(bundled):
            return
    version = bundled
    release = RELEASES_ROOT / f"bundled-{version}"
    if release.exists():
        shutil.rmtree(release)
    shutil.copytree(BASE_ROOT, release)
    atomic_switch_release(release)
    write_json_atomic(STATE_PATH, {
        "active_version": version,
        "active_release": str(release),
        "initialized_at": now_iso(),
        "source": "bundled",
    })


def child_env(release: Path) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = str(release)
    env["COCKLEBUR_MANAGED_RUNTIME"] = "1"
    env["COCKLEBUR_RUNTIME_DIR"] = str(RUNTIME_ROOT)
    return env


def start_child(release: Path) -> subprocess.Popen[Any]:
    cmd = [
        sys.executable, "-m", "uvicorn", "app.main:app",
        "--host", "0.0.0.0", "--port", str(PORT), "--workers", "1", "--proxy-headers",
    ]
    return subprocess.Popen(cmd, cwd=release, env=child_env(release))


def stop_child(child: subprocess.Popen[Any] | None, timeout: float = 15.0) -> None:
    if child is None or child.poll() is not None:
        return
    child.terminate()
    try:
        child.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        child.kill()
        child.wait(timeout=5)


def wait_health(expected_version: str, child: subprocess.Popen[Any], timeout: float = 45.0) -> tuple[bool, str]:
    deadline = time.monotonic() + timeout
    last = "health check did not complete"
    while time.monotonic() < deadline:
        if child.poll() is not None:
            return False, f"server process exited with code {child.returncode}"
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=2) as response:
                body = json.loads(response.read().decode("utf-8"))
            actual = str(body.get("version") or "")
            if body.get("status") == "ok" and actual == expected_version:
                return True, "ok"
            last = f"health returned version {actual!r}, expected {expected_version!r}"
        except Exception as exc:
            last = str(exc)
        time.sleep(0.5)
    return False, last


def validate_staged(stage_id: str) -> tuple[Path, dict[str, Any]]:
    stage_root = DATA_ROOT / ".updates" / stage_id
    state_path = stage_root / "stage.json"
    state = read_json(state_path)
    if not isinstance(state, dict):
        raise RuntimeError("staged update state is missing")
    extracted = stage_root / "payload"
    manifest = read_json(extracted / "update-manifest.json")
    checksums = read_json(extracted / "checksums.json")
    if not isinstance(manifest, dict) or not isinstance(checksums, dict):
        raise RuntimeError("staged update manifest/checksums are missing")
    if manifest.get("format") != "cocklebur-server-update" or str(manifest.get("format_version")) != "1.1":
        raise RuntimeError("managed updater requires update package format 1.1")
    if manifest.get("apply_mode") != "managed-runtime-v1":
        raise RuntimeError("unsupported managed update apply mode")
    target = str(manifest.get("target_version") or "")
    if not target:
        raise RuntimeError("target version is missing")
    for rel, expected in checksums.items():
        rel = str(rel)
        candidate = (extracted / rel).resolve()
        if extracted.resolve() not in candidate.parents or not candidate.is_file():
            raise RuntimeError(f"invalid update checksum path: {rel}")
        if sha256(candidate) != str(expected):
            raise RuntimeError(f"checksum mismatch: {rel}")
    payload = extracted / "payload"
    if not (payload / "app" / "__init__.py").is_file() or not (payload / "requirements.txt").is_file():
        raise RuntimeError("runtime payload is incomplete")
    actual_target = release_version(payload)
    if actual_target != target:
        raise RuntimeError(f"payload version {actual_target} does not match manifest target {target}")
    return payload, state


def requirements_compatible(current: Path, target: Path) -> bool:
    current_req = current / "requirements.txt"
    target_req = target / "requirements.txt"
    if not current_req.is_file() or not target_req.is_file():
        return False
    return current_req.read_bytes() == target_req.read_bytes()


def mark_stage(stage_id: str, **changes: Any) -> None:
    path = DATA_ROOT / ".updates" / stage_id / "stage.json"
    state = read_json(path, {})
    if not isinstance(state, dict):
        state = {"stage_id": stage_id}
    state.update(changes)
    write_json_atomic(path, state)


def cleanup_old_releases(keep: set[Path]) -> None:
    candidates = [p for p in RELEASES_ROOT.iterdir() if p.is_dir() and p not in keep]
    candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for path in candidates[3:]:
        shutil.rmtree(path, ignore_errors=True)


def apply_request(request: dict[str, Any]) -> None:
    global CHILD
    stage_id = str(request.get("stage_id") or "")
    if not stage_id:
        raise RuntimeError("apply request has no stage_id")
    current = CURRENT_LINK.resolve()
    current_version = release_version(current)
    payload, state = validate_staged(stage_id)
    target_version = str((state.get("manifest") or {}).get("target_version") or release_version(payload))
    if not requirements_compatible(current, payload):
        raise RuntimeError("managed-runtime-v1 cannot change Python dependencies; deploy a new base image for this update")

    release = RELEASES_ROOT / f"{target_version}-{stage_id}"
    if release.exists():
        shutil.rmtree(release)
    shutil.copytree(payload, release)
    mark_stage(stage_id, state="applying", apply_started_at=now_iso(), previous_version=current_version, previous_release=str(current))

    stop_child(CHILD)
    atomic_switch_release(release)
    candidate = start_child(release)
    ok, detail = wait_health(target_version, candidate, timeout=float((state.get("manifest") or {}).get("health_timeout_seconds") or 45))
    if ok:
        CHILD = candidate
        write_json_atomic(STATE_PATH, {
            "active_version": target_version,
            "active_release": str(release),
            "previous_version": current_version,
            "previous_release": str(current),
            "updated_at": now_iso(),
            "stage_id": stage_id,
        })
        mark_stage(stage_id, state="applied", applied_at=now_iso(), error=None)
        cleanup_old_releases({release, current})
        return

    stop_child(candidate)
    atomic_switch_release(current)
    rollback = start_child(current)
    rollback_ok, rollback_detail = wait_health(current_version, rollback, timeout=30)
    CHILD = rollback
    error = f"Update health check failed: {detail}"
    if not rollback_ok:
        error += f"; rollback health check also failed: {rollback_detail}"
    write_json_atomic(STATE_PATH, {
        "active_version": current_version,
        "active_release": str(current),
        "rollback_from": target_version,
        "rollback_at": now_iso(),
        "stage_id": stage_id,
        "error": error,
    })
    mark_stage(stage_id, state="rolled_back", rolled_back_at=now_iso(), error=error)


def signal_handler(_signum: int, _frame: Any) -> None:
    global STOPPING
    STOPPING = True


def main() -> int:
    global CHILD
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    initialize_runtime()
    active = CURRENT_LINK.resolve()
    CHILD = start_child(active)
    expected = release_version(active)
    ok, detail = wait_health(expected, CHILD, timeout=45)
    if not ok:
        print(f"Cocklebur supervisor: initial server failed health check: {detail}", file=sys.stderr, flush=True)
        stop_child(CHILD)
        return 1
    print(f"Cocklebur supervisor: running {expected} from {active}", flush=True)

    while not STOPPING:
        if CHILD.poll() is not None:
            print(f"Cocklebur supervisor: server exited unexpectedly ({CHILD.returncode}); restarting active release", file=sys.stderr, flush=True)
            time.sleep(1)
            CHILD = start_child(CURRENT_LINK.resolve())
        if APPLY_REQUEST.exists():
            request = read_json(APPLY_REQUEST, {})
            APPLY_REQUEST.unlink(missing_ok=True)
            try:
                apply_request(request if isinstance(request, dict) else {})
            except Exception as exc:
                stage_id = str(request.get("stage_id") or "") if isinstance(request, dict) else ""
                if stage_id:
                    mark_stage(stage_id, state="failed", failed_at=now_iso(), error=str(exc))
                print(f"Cocklebur supervisor: update failed before switch: {exc}", file=sys.stderr, flush=True)
        time.sleep(0.4)

    stop_child(CHILD)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
