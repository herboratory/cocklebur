from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tarfile
import tempfile
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__
from .config import Settings
from .storage import ValidationError

UPDATE_FORMAT = "cocklebur-server-update"
STAGING_FORMAT_VERSION = "1.0"
MANAGED_FORMAT_VERSION = "1.1"
SUPPORTED_FORMAT_VERSIONS = {STAGING_FORMAT_VERSION, MANAGED_FORMAT_VERSION}
MANAGED_APPLY_MODE = "managed-runtime-v1"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _version_tuple(value: str) -> tuple[int, ...]:
    nums = [int(x) for x in re.findall(r"\d+", value or "")[:4]]
    return tuple(nums or [0])


class UpdateCenter:
    """Validate, back up, stage, and request managed-runtime updates.

    The web process never talks to Docker/Kubernetes and never replaces its own
    process. In a managed deployment, a tiny PID-1 supervisor watches a local
    control file under the persistent data volume, independently revalidates the
    staged package, atomically switches the runtime release, restarts Uvicorn,
    health-checks it, and rolls back the code release on failure.
    """

    def __init__(self, settings: Settings, store: Any | None = None):
        self.settings = settings
        self.store = store
        self.root = settings.data_dir / ".updates"
        self.backups = settings.data_dir / ".update_backups"
        self.runtime_root = Path(os.getenv("COCKLEBUR_RUNTIME_DIR", str(settings.data_dir / ".runtime"))).expanduser().resolve()
        self.control_root = self.runtime_root / "control"
        self.root.mkdir(parents=True, exist_ok=True)
        self.backups.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _sha256(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def managed_runtime_supported(self) -> bool:
        return (
            os.getenv("COCKLEBUR_MANAGED_RUNTIME", "").strip() == "1"
            and self.control_root.is_dir()
        )

    def _safe_extract(self, zip_path: Path, dest: Path) -> None:
        if not zipfile.is_zipfile(zip_path):
            raise ValidationError("Not a valid update ZIP")
        limit = self.settings.max_update_mb * 1024 * 1024
        with zipfile.ZipFile(zip_path) as zf:
            total = sum(i.file_size for i in zf.infolist())
            if total > limit:
                raise ValidationError("Update expands beyond the configured update limit")
            for info in zf.infolist():
                name = info.filename
                if name.startswith(("/", "\\")) or ".." in Path(name).parts:
                    raise ValidationError("Unsafe update ZIP path")
                target = (dest / name).resolve()
                if dest.resolve() not in target.parents and target != dest.resolve():
                    raise ValidationError("Unsafe update ZIP path")
            zf.extractall(dest)

    def _validate_extracted(self, root: Path) -> dict[str, Any]:
        manifest_path = root / "update-manifest.json"
        checksum_path = root / "checksums.json"
        if not manifest_path.exists() or not checksum_path.exists():
            raise ValidationError("Update requires update-manifest.json and checksums.json")
        manifest = json.loads(manifest_path.read_text("utf-8"))
        checksums = json.loads(checksum_path.read_text("utf-8"))
        format_version = str(manifest.get("format_version") or "")
        if manifest.get("format") != UPDATE_FORMAT or format_version not in SUPPORTED_FORMAT_VERSIONS:
            raise ValidationError("Unsupported update package format")
        target = str(manifest.get("target_version") or manifest.get("version") or "").strip()
        minimum = str(manifest.get("minimum_source_version") or "0").strip()
        if not target:
            raise ValidationError("Update manifest is missing target_version")
        if _version_tuple(__version__) < _version_tuple(minimum):
            raise ValidationError(f"Update requires Cocklebur {minimum} or newer")
        if _version_tuple(target) <= _version_tuple(__version__):
            raise ValidationError(f"Target version {target} is not newer than current {__version__}")
        if not isinstance(checksums, dict) or not checksums:
            raise ValidationError("checksums.json must contain file checksums")

        forbidden_roots = {"data", ".git", ".github"}
        forbidden_names = {".env", ".instance_secret", ".instance_id", ".host_key", ".instance_auth.json"}
        payload_files: set[str] = set()
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if rel in {"update-manifest.json", "checksums.json"}:
                continue
            parts = Path(rel).parts
            if not parts or parts[0] in forbidden_roots or Path(rel).name in forbidden_names:
                raise ValidationError(f"Update package contains forbidden runtime path: {rel}")
            payload_files.add(rel)
        checksum_files = {str(k) for k in checksums}
        missing = sorted(payload_files - checksum_files)
        extra = sorted(checksum_files - payload_files)
        if missing:
            raise ValidationError(f"Update package has unchecked files: {missing[0]}")
        if extra:
            raise ValidationError(f"Update checksum references a missing file: {extra[0]}")
        for rel, expected in checksums.items():
            rel = str(rel)
            path = (root / rel).resolve()
            if root.resolve() not in path.parents or not path.is_file():
                raise ValidationError(f"Update checksum references an invalid file: {rel}")
            if self._sha256(path) != str(expected):
                raise ValidationError(f"Update checksum mismatch: {rel}")

        apply_mode = str(manifest.get("apply_mode") or "")
        if format_version == MANAGED_FORMAT_VERSION:
            if apply_mode != MANAGED_APPLY_MODE:
                raise ValidationError("Managed update package has an unsupported apply_mode")
            runtime_payload = root / "payload"
            if not (runtime_payload / "app" / "__init__.py").is_file():
                raise ValidationError("Managed update payload is missing app/__init__.py")
            if not (runtime_payload / "requirements.txt").is_file():
                raise ValidationError("Managed update payload is missing requirements.txt")

        return {
            **manifest,
            "format_version": format_version,
            "target_version": target,
            "minimum_source_version": minimum,
            "current_version": __version__,
            "restart_required": bool(manifest.get("restart_required", True)),
            "apply_mode": apply_mode or None,
        }

    def _create_data_backup(self, stage_id: str) -> Path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out = self.backups / f"Cocklebur_Data_PreUpdate_{stamp}_{stage_id}.tar.gz"
        transient = {".updates", ".update_backups", ".imports", ".exports", ".runtime", "__pycache__"}

        def tar_filter(info: tarfile.TarInfo) -> tarfile.TarInfo | None:
            name = Path(info.name).name
            if name.endswith(".lock") or name.endswith(".tmp"):
                return None
            return info

        with tarfile.open(out, "w:gz") as tf:
            for child in sorted(self.settings.data_dir.iterdir(), key=lambda p: p.name):
                if child.name in transient or child.name.endswith(".lock"):
                    continue
                if self.store is not None and child.is_dir() and child.name.startswith("p_"):
                    with self.store.project_lock(child.name):
                        tf.add(child, arcname=child.name, recursive=True, filter=tar_filter)
                else:
                    tf.add(child, arcname=child.name, recursive=True, filter=tar_filter)
        return out

    @staticmethod
    def _write_json_atomic(path: Path, obj: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", "utf-8")
        os.replace(tmp, path)

    def _read_stage(self, stage_id: str) -> tuple[Path, dict[str, Any]]:
        stage_root = self.root / str(stage_id)
        state_path = stage_root / "stage.json"
        if not state_path.is_file():
            raise ValidationError("Staged update no longer exists")
        state = json.loads(state_path.read_text("utf-8"))
        return state_path, state

    def stage(self, zip_path: Path, original_name: str = "update.zip") -> dict[str, Any]:
        with tempfile.TemporaryDirectory(prefix="cocklebur_update_validate_") as td:
            extracted = Path(td) / "extracted"
            extracted.mkdir()
            self._safe_extract(zip_path, extracted)
            manifest = self._validate_extracted(extracted)
            stage_id = "upd_" + uuid.uuid4().hex[:16]
            stage_root = self.root / stage_id
            stage_root.mkdir(parents=True, exist_ok=False)
            try:
                package_path = stage_root / "package.zip"
                shutil.copy2(zip_path, package_path)
                payload = stage_root / "payload"
                shutil.copytree(extracted, payload)
                backup = self._create_data_backup(stage_id)
            except Exception:
                shutil.rmtree(stage_root, ignore_errors=True)
                raise
            can_apply = (
                self.managed_runtime_supported()
                and manifest.get("format_version") == MANAGED_FORMAT_VERSION
                and manifest.get("apply_mode") == MANAGED_APPLY_MODE
            )
            state = {
                "stage_id": stage_id,
                "original_name": original_name,
                "staged_at": now_iso(),
                "package_sha256": self._sha256(package_path),
                "package_path": str(package_path),
                "payload_path": str(payload),
                "backup_path": str(backup),
                "apply_supported": can_apply,
                "state": "staged",
                "manifest": manifest,
            }
            self._write_json_atomic(stage_root / "stage.json", state)
            self._write_json_atomic(self.root / "current.json", {"stage_id": stage_id})
            return state

    def status(self) -> dict[str, Any]:
        pointer = self.root / "current.json"
        managed = self.managed_runtime_supported()
        if not pointer.exists():
            return {"current_version": __version__, "staged": None, "apply_supported": managed}
        try:
            stage_id = json.loads(pointer.read_text("utf-8")).get("stage_id")
            _state_path, state = self._read_stage(str(stage_id))
            state["apply_supported"] = bool(
                managed
                and state.get("manifest", {}).get("format_version") == MANAGED_FORMAT_VERSION
                and state.get("manifest", {}).get("apply_mode") == MANAGED_APPLY_MODE
            )
            return {"current_version": __version__, "staged": state, "apply_supported": managed}
        except Exception:
            return {"current_version": __version__, "staged": None, "apply_supported": managed}

    def request_apply(self) -> dict[str, Any]:
        if not self.managed_runtime_supported():
            raise ValidationError("This deployment does not have the managed updater supervisor enabled")
        status = self.status()
        staged = status.get("staged") or {}
        stage_id = staged.get("stage_id")
        if not stage_id:
            raise ValidationError("No update is staged")
        if staged.get("state") not in {"staged", "rolled_back", "failed"}:
            raise ValidationError(f"Update cannot be applied from state: {staged.get('state')}")
        manifest = staged.get("manifest") or {}
        if manifest.get("format_version") != MANAGED_FORMAT_VERSION or manifest.get("apply_mode") != MANAGED_APPLY_MODE:
            raise ValidationError("This package can be staged but is not executable by the managed updater")

        state_path, state = self._read_stage(str(stage_id))
        requested_at = now_iso()
        state["state"] = "apply_requested"
        state["apply_requested_at"] = requested_at
        state.pop("error", None)
        self._write_json_atomic(state_path, state)
        request = {
            "stage_id": str(stage_id),
            "target_version": str(manifest.get("target_version") or ""),
            "requested_at": requested_at,
        }
        self._write_json_atomic(self.control_root / "apply-request.json", request)
        return {"ok": True, "state": "apply_requested", **request}

    def cancel(self) -> dict[str, Any]:
        status = self.status()
        staged = status.get("staged") or {}
        stage_id = staged.get("stage_id")
        if staged.get("state") == "apply_requested":
            raise ValidationError("Update apply has already been requested")
        if stage_id:
            shutil.rmtree(self.root / str(stage_id), ignore_errors=True)
        (self.root / "current.json").unlink(missing_ok=True)
        return {"ok": True, "backup_preserved": staged.get("backup_path")}
