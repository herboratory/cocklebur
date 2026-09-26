from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import tempfile
import uuid
import zipfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from filelock import FileLock

from . import __version__
from .config import Settings
from .models import now_iso
from .security import new_recovery_code, new_token, safe_filename, safe_id, token_hash

FORMAT_NAME = "popup-workspace-pack"
FORMAT_VERSION = "1.0"
INSTANCE_AUTH_VERSION = 1


class NotFoundError(Exception):
    pass


class ConflictError(Exception):
    def __init__(self, message: str, current: dict[str, Any] | None = None):
        super().__init__(message)
        self.current = current


class ValidationError(Exception):
    pass


class PermissionError_(Exception):
    pass


class CapsuleStore:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.root = settings.data_dir
        self.root.mkdir(parents=True, exist_ok=True)

    def _registry_path(self) -> Path:
        return self.root / ".project_registry.json"

    def _registry(self) -> dict[str, str]:
        path = self._registry_path()
        if not path.exists(): return {}
        try: return self._read_json(path, {})
        except Exception: return {}

    def _register_root(self, project_id: str, root: Path) -> None:
        path = self._registry_path()
        lock = FileLock(str(path) + ".lock", timeout=15)
        with lock:
            registry = self._read_json(path, {}) if path.exists() else {}
            registry[project_id] = str(root.resolve())
            self._atomic_write_json(path, registry)

    def _unregister_root(self, project_id: str) -> None:
        path = self._registry_path()
        if not path.exists(): return
        lock = FileLock(str(path) + ".lock", timeout=15)
        with lock:
            registry = self._read_json(path, {})
            registry.pop(project_id, None)
            self._atomic_write_json(path, registry)

    def project_root(self, project_id: str) -> Path:
        safe_id(project_id, "project id")
        custom = self._registry().get(project_id)
        return Path(custom).resolve() if custom else self.root / project_id

    def exists(self, project_id: str) -> bool:
        return (self.project_root(project_id) / "project.json").exists()

    def _path(self, project_id: str, rel: str) -> Path:
        root = self.project_root(project_id).resolve()
        path = (root / rel).resolve()
        if root != path and root not in path.parents:
            raise ValidationError("Unsafe path")
        return path

    @contextmanager
    def project_lock(self, project_id: str, timeout: int = 15):
        root = self.project_root(project_id)
        root.mkdir(parents=True, exist_ok=True)
        lock = FileLock(str(root / ".project.lock"), timeout=timeout)
        with lock:
            yield

    @staticmethod
    def _atomic_write_json(path: Path, data: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                json.dump(data, fh, ensure_ascii=False, indent=2, sort_keys=False)
                fh.write("\n")
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp_name, path)
            try:
                dir_fd = os.open(path.parent, os.O_DIRECTORY)
                try:
                    os.fsync(dir_fd)
                finally:
                    os.close(dir_fd)
            except (AttributeError, OSError):
                pass
        finally:
            if os.path.exists(tmp_name):
                os.unlink(tmp_name)

    @staticmethod
    def _read_json(path: Path, default: Any = None) -> Any:
        if not path.exists():
            if default is not None:
                return copy.deepcopy(default)
            raise NotFoundError(str(path))
        try:
            with path.open("r", encoding="utf-8") as fh:
                return json.load(fh)
        except json.JSONDecodeError as exc:
            backup = path.with_suffix(path.suffix + ".bak")
            if backup.exists():
                try:
                    with backup.open("r", encoding="utf-8") as fh:
                        return json.load(fh)
                except json.JSONDecodeError:
                    pass
            raise ValidationError(f"Corrupt JSON: {path.name}") from exc

    @staticmethod
    def _backup(path: Path) -> None:
        if path.exists() and path.is_file():
            shutil.copy2(path, path.with_suffix(path.suffix + ".bak"))

    @staticmethod
    def _append_jsonl(path: Path, item: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        lock = FileLock(str(path) + ".lock", timeout=15)
        line = json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n"
        with lock:
            with path.open("a", encoding="utf-8") as fh:
                fh.write(line)
                fh.flush()
                os.fsync(fh.fileno())

    @staticmethod
    def _read_jsonl(path: Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        out: list[dict[str, Any]] = []
        with path.open("r", encoding="utf-8") as fh:
            for n, line in enumerate(fh, 1):
                if not line.strip():
                    continue
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError as exc:
                    raise ValidationError(f"Corrupt JSONL {path.name} line {n}") from exc
        return out

    def _new_id(self, prefix: str) -> str:
        return f"{prefix}_{uuid.uuid4().hex[:16]}"

    def create_project(self, payload: dict[str, Any]) -> tuple[dict[str, Any], str | None, str]:
        project_id = self._new_id("p")
        storage_path = payload.get("storage_path")
        if storage_path and payload.get("mode", "local") == "local" and self.settings.app_mode == "local":
            parent = Path(storage_path).expanduser().resolve()
            parent.mkdir(parents=True, exist_ok=True)
            root = parent / project_id
            self._register_root(project_id, root)
        else:
            root = self.project_root(project_id)
        root.mkdir(parents=True)
        for rel in ["cards", "discussions/general", "files"]:
            (root / rel).mkdir(parents=True, exist_ok=True)
        ts = now_iso()
        mode = payload.get("mode", "local")
        project = {
            "id": project_id,
            "version": 1,
            "name": payload["name"],
            "description": payload.get("description", ""),
            "mode": mode,
            "status": "active",
            "expiry": payload.get("expiry"),
            "timezone": payload.get("timezone", "UTC"),
            "created_at": ts,
            "updated_at": ts,
            "content_updated_at": ts,
            "canonical_instance_id": self.settings.instance_id,
            "source_snapshot_instance_id": None,
            "last_export_at": None,
            "last_export_digest": None,
        }
        manifest = {
            "format": FORMAT_NAME,
            "format_version": FORMAT_VERSION,
            "project_id": project_id,
            "created_at": ts,
            "app_version": __version__,
        }
        owner_id = self._new_id("u")
        owner_token: str | None = None
        owner_recovery_code = new_recovery_code()
        owner = {
            "id": owner_id,
            "display_name": payload.get("owner_name") or "Owner",
            "role": "owner",
            "joined_at": ts,
            "access_hashes": [],
            "last_seen": {},
            "owner_recovery_hash": token_hash(owner_recovery_code),
            "owner_recovery_updated_at": ts,
        }
        if mode == "server":
            owner_token = new_token()
            owner["access_hashes"].append(token_hash(owner_token))
        settings = {
            "version": 1,
            "expiry": payload.get("expiry"),
            "quota_mb": self.settings.default_project_quota_mb,
            "invite_hash": None,
            "pin_hash": None,
            "invite_created_at": None,
        }
        channels = [{
            "id": "general",
            "name": "general",
            "visibility": "everyone",
            "roles": [],
            "members": [],
            "created_at": ts,
            "created_by": owner_id,
        }]
        self._atomic_write_json(root / "manifest.json", manifest)
        self._atomic_write_json(root / "project.json", project)
        self._atomic_write_json(root / "people.json", [owner])
        self._atomic_write_json(root / "files.json", [])
        self._atomic_write_json(root / "settings.json", settings)
        self._atomic_write_json(root / "discussions" / "channels.json", channels)
        self._append_jsonl(root / "activity.jsonl", {"id": self._new_id("a"), "ts": ts, "actor_id": owner_id, "actor_name": owner["display_name"], "type": "project.created", "summary": payload["name"]})
        return project, owner_token, owner_recovery_code

    def list_local_projects(self) -> list[dict[str, Any]]:
        projects = []
        roots = {p.resolve() for p in self.root.glob("p_*")}
        for _pid, custom in self._registry().items():
            roots.add(Path(custom).resolve())
        for p in sorted(roots, key=lambda x: str(x)):
            if (p / "project.json").exists():
                try:
                    obj = self._read_json(p / "project.json")
                    obj["storage_path"] = str(p.parent) if p.parent != self.root else None
                    projects.append(obj)
                except Exception:
                    continue
        projects.sort(key=lambda x: x.get("content_updated_at", ""), reverse=True)
        return projects

    def list_project_ids(self) -> list[str]:
        ids: set[str] = set()
        for root in self.root.glob("p_*"):
            if root.is_dir() and (root / "project.json").exists():
                ids.add(root.name)
        for pid, custom in self._registry().items():
            try:
                if (Path(custom).resolve() / "project.json").exists():
                    ids.add(pid)
            except Exception:
                continue
        return sorted(ids)

    def get_project(self, project_id: str) -> dict[str, Any]:
        return self._read_json(self._path(project_id, "project.json"))

    def get_manifest(self, project_id: str) -> dict[str, Any]:
        return self._read_json(self._path(project_id, "manifest.json"))

    def get_settings(self, project_id: str) -> dict[str, Any]:
        return self._read_json(self._path(project_id, "settings.json"))

    def update_project(self, project_id: str, patch: dict[str, Any], actor_id: str) -> dict[str, Any]:
        with self.project_lock(project_id):
            path = self._path(project_id, "project.json")
            obj = self._read_json(path)
            expected = patch.pop("expected_version")
            if obj["version"] != expected:
                raise ConflictError("Project was updated", obj)
            for key in ["name", "description", "expiry", "timezone"]:
                if key in patch and patch[key] is not None:
                    obj[key] = patch[key]
            obj["version"] += 1
            obj["updated_at"] = now_iso()
            obj["content_updated_at"] = obj["updated_at"]
            self._backup(path)
            self._atomic_write_json(path, obj)
            self._activity_unlocked(project_id, actor_id, "project.updated", obj["name"])
            return obj

    def _touch_content_unlocked(self, project_id: str) -> None:
        path = self._path(project_id, "project.json")
        project = self._read_json(path)
        project["content_updated_at"] = now_iso()
        self._atomic_write_json(path, project)

    def _activity_unlocked(self, project_id: str, actor_id: str, kind: str, summary: str, meta: dict[str, Any] | None = None) -> dict[str, Any]:
        actor_name = "System" if actor_id == "system" else actor_id
        if actor_id != "system":
            try:
                actor_name = next((p.get("display_name") for p in self.people(project_id) if p.get("id") == actor_id), None) or actor_id
            except Exception:
                pass
        item = {
            "id": self._new_id("a"),
            "ts": now_iso(),
            "actor_id": actor_id,
            "actor_name": actor_name,
            "type": kind,
            "summary": summary,
            "meta": meta or {},
        }
        self._append_jsonl(self._path(project_id, "activity.jsonl"), item)
        return item

    def activity(self, project_id: str, limit: int = 100) -> list[dict[str, Any]]:
        return list(reversed(self._read_jsonl(self._path(project_id, "activity.jsonl"))))[:limit]

    def activity_for_person(self, project_id: str, person: dict[str, Any], limit: int = 100) -> list[dict[str, Any]]:
        """Return project activity without leaking creator-only Card activity.

        Card visibility is resolved from the current card when it still exists, so changing a
        card back to Everyone makes its history visible again. For deleted cards, the
        visibility/creator snapshot stored in activity metadata is used.
        """
        person_id = person.get("id")
        current_cards = {c.get("id"): c for c in self.cards(project_id)}
        out: list[dict[str, Any]] = []
        for item in self.activity(project_id, 10000):
            meta = item.get("meta") or {}
            card_id = meta.get("card_id")
            if card_id:
                card = current_cards.get(card_id)
                visibility = (card or {}).get("visibility", meta.get("visibility", "everyone"))
                creator_id = (card or {}).get("created_by", meta.get("creator_id"))
                if visibility == "private" and creator_id != person_id:
                    continue
            out.append(item)
            if len(out) >= limit:
                break
        return out

    # ---- Instance Host / delegated instance permissions ----
    def _instance_auth_path(self) -> Path:
        return self.root / ".instance_auth.json"

    @staticmethod
    def _instance_auth_default() -> dict[str, Any]:
        return {"version": INSTANCE_AUTH_VERSION, "host": None, "grants": []}

    def _read_instance_auth(self) -> dict[str, Any]:
        path = self._instance_auth_path()
        obj = self._read_json(path, self._instance_auth_default()) if path.exists() else self._instance_auth_default()
        if not isinstance(obj, dict):
            raise ValidationError("Corrupt instance auth state")
        obj.setdefault("version", INSTANCE_AUTH_VERSION)
        obj.setdefault("host", None)
        obj.setdefault("grants", [])
        if not isinstance(obj["grants"], list):
            obj["grants"] = []
        return obj

    def host_claimed(self) -> bool:
        return bool(self._read_instance_auth().get("host"))

    @staticmethod
    def _public_host(host: dict[str, Any] | None) -> dict[str, Any] | None:
        if not host:
            return None
        return {k: host.get(k) for k in ["display_name", "claimed_at", "recovery_updated_at"]}

    def claim_host(self, display_name: str) -> tuple[dict[str, Any], str, str]:
        path = self._instance_auth_path()
        lock = FileLock(str(path) + ".lock", timeout=15)
        with lock:
            obj = self._read_json(path, self._instance_auth_default()) if path.exists() else self._instance_auth_default()
            if obj.get("host"):
                raise ConflictError("This Cocklebur instance already has a Host")
            access = new_token()
            recovery = new_recovery_code()
            ts = now_iso()
            host = {
                "display_name": (display_name or "Host").strip()[:100] or "Host",
                "claimed_at": ts,
                "access_hashes": [token_hash(access)],
                "recovery_hash": token_hash(recovery),
                "recovery_updated_at": ts,
            }
            obj = {"version": INSTANCE_AUTH_VERSION, "host": host, "grants": obj.get("grants", []) or []}
            self._atomic_write_json(path, obj)
            return self._public_host(host) or {}, access, recovery

    def resolve_host(self, token: str | None) -> dict[str, Any] | None:
        if not token:
            return None
        host = self._read_instance_auth().get("host")
        if not host:
            return None
        h = token_hash(token)
        if h in (host.get("access_hashes") or []):
            return self._public_host(host)
        return None

    def recover_host(self, code: str) -> tuple[dict[str, Any], str, str]:
        path = self._instance_auth_path()
        lock = FileLock(str(path) + ".lock", timeout=15)
        with lock:
            obj = self._read_json(path, self._instance_auth_default()) if path.exists() else self._instance_auth_default()
            host = obj.get("host")
            if not host:
                raise ValidationError("This Cocklebur instance has not been claimed by a Host yet")
            if token_hash((code or "").strip().upper()) != host.get("recovery_hash"):
                raise PermissionError_("Invalid Host recovery code")
            access = new_token()
            recovery = new_recovery_code()
            hashes = [x for x in (host.get("access_hashes") or []) if x]
            hashes.append(token_hash(access))
            host["access_hashes"] = hashes[-8:]
            host["recovery_hash"] = token_hash(recovery)
            host["recovery_updated_at"] = now_iso()
            self._atomic_write_json(path, obj)
            return self._public_host(host) or {}, access, recovery

    def rotate_host_recovery(self) -> str:
        path = self._instance_auth_path()
        lock = FileLock(str(path) + ".lock", timeout=15)
        with lock:
            obj = self._read_json(path, self._instance_auth_default()) if path.exists() else self._instance_auth_default()
            host = obj.get("host")
            if not host:
                raise ValidationError("This Cocklebur instance has not been claimed by a Host yet")
            recovery = new_recovery_code()
            host["recovery_hash"] = token_hash(recovery)
            host["recovery_updated_at"] = now_iso()
            self._atomic_write_json(path, obj)
            return recovery

    def reset_host_claim(self) -> Path | None:
        """Break-glass reset of instance Host only; preserve projects and grants."""
        path = self._instance_auth_path()
        if not path.exists():
            return None
        lock = FileLock(str(path) + ".lock", timeout=15)
        with lock:
            obj = self._read_json(path, self._instance_auth_default())
            stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = self.root / f".instance_auth.json.bak-{stamp}"
            shutil.copy2(path, backup)
            obj.setdefault("version", INSTANCE_AUTH_VERSION)
            obj.setdefault("grants", [])
            obj["host"] = None
            self._atomic_write_json(path, obj)
            return backup

    def instance_grants(self) -> list[dict[str, Any]]:
        return [dict(x) for x in self._read_instance_auth().get("grants", []) if isinstance(x, dict)]

    def set_instance_permissions(self, project_id: str, person_id: str, *, can_create_projects: bool, can_import_projects: bool) -> dict[str, Any]:
        person = self.person(project_id, person_id)
        project = self.get_project(project_id)
        path = self._instance_auth_path()
        lock = FileLock(str(path) + ".lock", timeout=15)
        with lock:
            obj = self._read_json(path, self._instance_auth_default()) if path.exists() else self._instance_auth_default()
            grants = [g for g in (obj.get("grants") or []) if not (g.get("project_id") == project_id and g.get("person_id") == person_id)]
            if can_create_projects or can_import_projects:
                grants.append({
                    "project_id": project_id,
                    "person_id": person_id,
                    "can_create_projects": bool(can_create_projects),
                    "can_import_projects": bool(can_import_projects),
                    "updated_at": now_iso(),
                })
            obj["grants"] = grants
            self._atomic_write_json(path, obj)
        return {
            "project_id": project_id,
            "project_name": project.get("name", project_id),
            "person_id": person_id,
            "display_name": person.get("display_name", person_id),
            "role": person.get("role", "member"),
            "can_create_projects": bool(can_create_projects),
            "can_import_projects": bool(can_import_projects),
        }

    def remove_instance_grant(self, project_id: str, person_id: str | None = None) -> None:
        path = self._instance_auth_path()
        if not path.exists():
            return
        lock = FileLock(str(path) + ".lock", timeout=15)
        with lock:
            obj = self._read_json(path, self._instance_auth_default())
            before = obj.get("grants") or []
            if person_id is None:
                obj["grants"] = [g for g in before if g.get("project_id") != project_id]
            else:
                obj["grants"] = [g for g in before if not (g.get("project_id") == project_id and g.get("person_id") == person_id)]
            self._atomic_write_json(path, obj)

    def instance_people_catalog(self) -> list[dict[str, Any]]:
        grants = {(g.get("project_id"), g.get("person_id")): g for g in self.instance_grants()}
        out: list[dict[str, Any]] = []
        roots = {p.resolve() for p in self.root.glob("p_*") if p.is_dir()}
        for _pid, custom in self._registry().items():
            roots.add(Path(custom).resolve())
        for root in sorted(roots, key=lambda x: str(x)):
            if not (root / "project.json").exists() or not (root / "people.json").exists():
                continue
            try:
                project = self._read_json(root / "project.json")
                if project.get("mode") != "server":
                    continue
                for person in self._read_json(root / "people.json", []):
                    grant = grants.get((project.get("id"), person.get("id")), {})
                    out.append({
                        "project_id": project.get("id"),
                        "project_name": project.get("name", project.get("id")),
                        "person_id": person.get("id"),
                        "display_name": person.get("display_name", person.get("id")),
                        "role": person.get("role", "member"),
                        "can_create_projects": bool(grant.get("can_create_projects")),
                        "can_import_projects": bool(grant.get("can_import_projects")),
                    })
            except (ValidationError, NotFoundError):
                continue
        out.sort(key=lambda x: (str(x.get("display_name", "")).casefold(), str(x.get("project_name", "")).casefold()))
        return out

    # ---- People / auth ----
    def people(self, project_id: str) -> list[dict[str, Any]]:
        return self._read_json(self._path(project_id, "people.json"), [])

    def person(self, project_id: str, person_id: str) -> dict[str, Any]:
        safe_id(person_id, "person id")
        for p in self.people(project_id):
            if p["id"] == person_id:
                return p
        raise NotFoundError("person")

    def resolve_access(self, project_id: str, token: str | None) -> dict[str, Any] | None:
        project = self.get_project(project_id)
        if project.get("mode") == "local" and self.settings.app_mode == "local":
            ps = self.people(project_id)
            return ps[0] if ps else {"id": "local", "display_name": "Local Owner", "role": "owner"}
        if not token:
            return None
        h = token_hash(token)
        for person in self.people(project_id):
            if h in person.get("access_hashes", []):
                return person
        return None

    def make_invite(self, project_id: str, actor_id: str, pin: str | None = None) -> str:
        from .security import hash_pin
        token = new_token()
        with self.project_lock(project_id):
            path = self._path(project_id, "settings.json")
            obj = self._read_json(path)
            obj["invite_hash"] = token_hash(token)
            obj["invite_created_at"] = now_iso()
            if pin is not None:
                obj["pin_hash"] = hash_pin(pin) if pin else None
            obj["version"] += 1
            self._atomic_write_json(path, obj)
            self._activity_unlocked(project_id, actor_id, "invite.regenerated", "Invite regenerated")
        return token

    def join(self, project_id: str, display_name: str, invite_token: str, pin: str | None) -> tuple[dict[str, Any], str]:
        from .security import verify_pin, verify_token
        with self.project_lock(project_id):
            settings = self.get_settings(project_id)
            if not settings.get("invite_hash") or not verify_token(invite_token, settings["invite_hash"]):
                raise PermissionError_("Invalid invite")
            if not verify_pin(pin or "", settings.get("pin_hash")):
                raise PermissionError_("Invalid PIN")
            access = new_token()
            person = {
                "id": self._new_id("u"),
                "display_name": display_name,
                "role": "member",
                "joined_at": now_iso(),
                "access_hashes": [token_hash(access)],
                "last_seen": {},
            }
            path = self._path(project_id, "people.json")
            people = self._read_json(path, [])
            people.append(person)
            self._atomic_write_json(path, people)
            self._touch_content_unlocked(project_id)
            self._activity_unlocked(project_id, person["id"], "member.joined", display_name)
            return person, access

    def update_person(self, project_id: str, person_id: str, patch: dict[str, Any], actor_id: str) -> dict[str, Any]:
        with self.project_lock(project_id):
            path = self._path(project_id, "people.json")
            people = self._read_json(path, [])
            target = next((p for p in people if p["id"] == person_id), None)
            if not target:
                raise NotFoundError("person")
            if patch.get("role") and target.get("role") == "owner" and patch["role"] != "owner":
                if sum(1 for p in people if p.get("role") == "owner") <= 1:
                    raise ValidationError("Cannot demote the last Owner")
            for k in ["role", "display_name"]:
                if patch.get(k) is not None:
                    target[k] = patch[k]
            self._atomic_write_json(path, people)
            self._touch_content_unlocked(project_id)
            self._activity_unlocked(project_id, actor_id, "member.updated", target["display_name"], {"person_id": person_id})
            return target

    def remove_person(self, project_id: str, person_id: str, actor_id: str) -> None:
        with self.project_lock(project_id):
            path = self._path(project_id, "people.json")
            people = self._read_json(path, [])
            target = next((p for p in people if p["id"] == person_id), None)
            if not target:
                raise NotFoundError("person")
            if target.get("role") == "owner" and sum(1 for p in people if p.get("role") == "owner") <= 1:
                raise ValidationError("Cannot remove the last Owner")
            people = [p for p in people if p["id"] != person_id]
            self._atomic_write_json(path, people)
            self._touch_content_unlocked(project_id)
            self._activity_unlocked(project_id, actor_id, "member.removed", target["display_name"])

    def issue_access(self, project_id: str, person_id: str, actor_id: str = "system") -> str:
        """Issue a fresh browser access token directly.

        Used when the current request is already trusted (for example a successful
        server-side pack import) so the browser can receive its owner cookie
        without a round-trip through an absolute recovery URL.
        """
        access = new_token()
        with self.project_lock(project_id):
            path = self._path(project_id, "people.json")
            people = self._read_json(path, [])
            target = next((p for p in people if p["id"] == person_id), None)
            if not target:
                raise NotFoundError("person")
            target["access_hashes"] = [token_hash(access)]
            target["recovery_hash"] = None
            self._atomic_write_json(path, people)
            self._activity_unlocked(project_id, actor_id, "member.access_issued", target["display_name"])
        return access

    @staticmethod
    def _append_access_hash(target: dict[str, Any], access: str, max_sessions: int = 8) -> None:
        """Add a browser session without invalidating other valid devices.

        Recovery restores access; it is not a stolen-device revocation flow. Keep a
        small bounded set of project-scoped browser credentials so Desktop/phone
        recovery cannot accidentally kick each other out.
        """
        h = token_hash(access)
        hashes = [x for x in (target.get("access_hashes") or []) if x and x != h]
        hashes.append(h)
        target["access_hashes"] = hashes[-max_sessions:]

    def regenerate_access(self, project_id: str, person_id: str, actor_id: str) -> str:
        """Issue a one-time recovery token without signing out existing devices."""
        token = new_token()
        with self.project_lock(project_id):
            path = self._path(project_id, "people.json")
            people = self._read_json(path, [])
            target = next((p for p in people if p["id"] == person_id), None)
            if not target:
                raise NotFoundError("person")
            target["recovery_hash"] = token_hash(token)
            self._atomic_write_json(path, people)
            self._activity_unlocked(project_id, actor_id, "member.access_regenerated", target["display_name"])
        return token

    def exchange_recovery(self, project_id: str, recovery_token: str) -> tuple[dict[str, Any], str]:
        h = token_hash(recovery_token)
        access = new_token()
        with self.project_lock(project_id):
            path = self._path(project_id, "people.json")
            people = self._read_json(path, [])
            target = next((p for p in people if p.get("recovery_hash") and h == p.get("recovery_hash")), None)
            if not target:
                raise PermissionError_("Invalid or expired recovery link")
            self._append_access_hash(target, access)
            target["recovery_hash"] = None
            self._atomic_write_json(path, people)
            self._activity_unlocked(project_id, target["id"], "member.recovered", target["display_name"])
            return target, access

    def rotate_owner_recovery(self, project_id: str, owner_id: str, actor_id: str = "system") -> str:
        code = new_recovery_code()
        with self.project_lock(project_id):
            path = self._path(project_id, "people.json")
            people = self._read_json(path, [])
            target = next((p for p in people if p.get("id") == owner_id), None)
            if not target:
                raise NotFoundError("person")
            if target.get("role") != "owner":
                raise ValidationError("Owner recovery can only be configured for an Owner")
            target["owner_recovery_hash"] = token_hash(code)
            target["owner_recovery_updated_at"] = now_iso()
            self._atomic_write_json(path, people)
            self._activity_unlocked(project_id, actor_id, "owner.recovery_rotated", target.get("display_name", "Owner"), {"person_id": owner_id})
        return code

    def recover_owner_code(self, project_id: str, code: str) -> tuple[dict[str, Any], str | None, str]:
        h = token_hash((code or "").strip().upper())
        access: str | None = None
        next_code = new_recovery_code()
        with self.project_lock(project_id):
            path = self._path(project_id, "people.json")
            people = self._read_json(path, [])
            target = next((p for p in people if p.get("role") == "owner" and p.get("owner_recovery_hash") == h), None)
            if not target:
                raise PermissionError_("Invalid owner recovery code")
            if self.get_project(project_id).get("mode") == "server":
                access = new_token()
                self._append_access_hash(target, access)
            target["recovery_hash"] = None
            target["owner_recovery_hash"] = token_hash(next_code)
            target["owner_recovery_updated_at"] = now_iso()
            self._atomic_write_json(path, people)
            self._activity_unlocked(project_id, target["id"], "owner.recovered", target.get("display_name", "Owner"), {"person_id": target["id"]})
            return target, access, next_code

    def card_activity(self, project_id: str, card_id: str, limit: int = 100) -> list[dict[str, Any]]:
        safe_id(card_id, "card id")
        return [a for a in self.activity(project_id, 10000) if a.get("meta", {}).get("card_id") == card_id][:limit]

    @staticmethod
    def _checklist_map(content: str) -> dict[int, tuple[bool, str]]:
        import re
        out: dict[int, tuple[bool, str]] = {}
        for idx, line in enumerate((content or "").splitlines()):
            m = re.match(r"^\s*(?:[-*]\s+)?\[( |x|X)\]\s+(.*)$", line)
            if m:
                out[idx] = (m.group(1).lower() == "x", m.group(2).strip())
        return out

    # ---- Cards ----
    def cards(self, project_id: str) -> list[dict[str, Any]]:
        out = []
        cards_dir = self._path(project_id, "cards")
        for p in sorted(cards_dir.glob("c_*.json")):
            if p.name.endswith(".bak"):
                continue
            try:
                out.append(self._read_json(p))
            except ValidationError:
                raise
        out.sort(key=lambda x: x.get("updated_at", ""), reverse=True)
        return out

    def get_card(self, project_id: str, card_id: str) -> dict[str, Any]:
        safe_id(card_id, "card id")
        return self._read_json(self._path(project_id, f"cards/{card_id}.json"))

    @staticmethod
    def _normalize_card_fields(card: dict[str, Any], previous_type: str | None = None) -> None:
        card_type = card.get("type") or "task"
        if card_type == "note":
            if card.get("status") not in {"active", "archived"}:
                old_status = card.get("status")
                card["status"] = "archived" if old_status in {"done", "happened", "archived"} else "active"
            card["start"] = None
            card["end"] = None
            card["all_day"] = False
            card["assignees"] = []
        elif previous_type == "note" and card.get("status") in {"active", "archived"}:
            card["status"] = "archived" if card.get("status") == "archived" else ("scheduled" if card_type == "event" else "todo")

    def _card_idempotency_path(self, project_id: str) -> Path:
        return self._path(project_id, ".card-create-idempotency.json")

    def create_card(self, project_id: str, payload: dict[str, Any], actor_id: str, idempotency_key: str | None = None) -> tuple[dict[str, Any], bool]:
        with self.project_lock(project_id):
            idem_path = self._card_idempotency_path(project_id)
            idem = self._read_json(idem_path, {}) if idem_path.exists() else {}
            scoped_key = None
            if idempotency_key:
                key = str(idempotency_key).strip()
                if len(key) > 160:
                    raise ValidationError("Idempotency key is too long")
                scoped_key = f"{actor_id}:{key}"
                prior = idem.get(scoped_key)
                if isinstance(prior, dict) and prior.get("card_id"):
                    try:
                        return self.get_card(project_id, prior["card_id"]), True
                    except NotFoundError:
                        idem.pop(scoped_key, None)
            cid = self._new_id("c")
            ts = now_iso()
            card_type = payload.get("type", "task")
            card = {
                "id": cid, "version": 1, "type": card_type, "title": payload["title"],
                "status": payload.get("status", "active" if card_type == "note" else "todo"),
                "start": payload.get("start"), "end": payload.get("end"),
                "all_day": payload.get("all_day", False), "assignees": payload.get("assignees", []),
                "description": payload.get("description", ""), "content": payload.get("content", ""),
                "tags": payload.get("tags", []), "linked_files": payload.get("linked_files", []),
                "edit_access": payload.get("edit_access", "public"),
                "visibility": payload.get("visibility", "everyone"),
                "created_by": actor_id, "updated_by": actor_id, "created_at": ts, "updated_at": ts,
            }
            self._normalize_card_fields(card)
            self._atomic_write_json(self._path(project_id, f"cards/{cid}.json"), card)
            if scoped_key:
                idem[scoped_key] = {"card_id": cid, "created_at": ts}
                if len(idem) > 300:
                    oldest = sorted(idem.items(), key=lambda kv: str((kv[1] or {}).get("created_at", "")))[:-250]
                    for old_key, _ in oldest:
                        idem.pop(old_key, None)
                self._atomic_write_json(idem_path, idem)
            self._touch_content_unlocked(project_id)
            self._activity_unlocked(project_id, actor_id, "card.created", card["title"], {"card_id": cid, "edit_access": card["edit_access"], "visibility": card["visibility"], "creator_id": actor_id})
            return card, False

    def update_card(self, project_id: str, card_id: str, patch: dict[str, Any], actor_id: str) -> dict[str, Any]:
        with self.project_lock(project_id):
            path = self._path(project_id, f"cards/{safe_id(card_id)}.json")
            card = self._read_json(path)
            before = copy.deepcopy(card)
            expected = patch.pop("expected_version")
            if card["version"] != expected:
                raise ConflictError("Card was updated while you were editing", card)
            for key, value in patch.items():
                if value is not None:
                    card[key] = value
            self._normalize_card_fields(card, before.get("type"))
            card.setdefault("edit_access", "public")
            card.setdefault("visibility", "everyone")
            card["version"] += 1
            card["updated_by"] = actor_id
            card["updated_at"] = now_iso()
            self._backup(path)
            self._atomic_write_json(path, card)
            self._touch_content_unlocked(project_id)

            meta_base = {"card_id": card_id, "visibility": card.get("visibility", "everyone"), "creator_id": card.get("created_by")}
            emitted = False
            old_checks = self._checklist_map(before.get("content", ""))
            new_checks = self._checklist_map(card.get("content", ""))
            checklist_only = before.get("content", "") != card.get("content", "")
            for idx in sorted(set(old_checks) & set(new_checks)):
                old_checked, old_text = old_checks[idx]
                new_checked, new_text = new_checks[idx]
                if old_text == new_text and old_checked != new_checked:
                    kind = "card.checklist_completed" if new_checked else "card.checklist_reopened"
                    self._activity_unlocked(project_id, actor_id, kind, card["title"], {**meta_base, "item": new_text, "line": idx})
                    emitted = True
                    # If every content difference is a checkbox marker, don't also add a generic content update.
                elif old_text != new_text:
                    checklist_only = False
            if set(old_checks) != set(new_checks):
                checklist_only = False
            # Compare content with checkbox markers stripped to recognize pure checkbox toggles.
            def strip_checks(v: str) -> str:
                import re
                return re.sub(r"^(\s*(?:[-*]\s+)?\[)[ xX](\]\s+)", r"\1?\2", v or "", flags=re.M)
            if before.get("content", "") != card.get("content", "") and strip_checks(before.get("content", "")) != strip_checks(card.get("content", "")):
                checklist_only = False
            if before.get("content", "") != card.get("content", "") and not checklist_only:
                self._activity_unlocked(project_id, actor_id, "card.content_updated", card["title"], meta_base)
                emitted = True
            if before.get("status") != card.get("status"):
                self._activity_unlocked(project_id, actor_id, "card.status_changed", card["title"], {**meta_base, "from": before.get("status"), "to": card.get("status")})
                emitted = True
            if before.get("title") != card.get("title"):
                self._activity_unlocked(project_id, actor_id, "card.title_updated", card["title"], {**meta_base, "from": before.get("title"), "to": card.get("title")})
                emitted = True
            if (before.get("edit_access") or "public") != (card.get("edit_access") or "public"):
                self._activity_unlocked(project_id, actor_id, "card.edit_access_changed", card["title"], {**meta_base, "from": before.get("edit_access", "public"), "to": card.get("edit_access", "public")})
                emitted = True
            if (before.get("visibility") or "everyone") != (card.get("visibility") or "everyone"):
                self._activity_unlocked(project_id, actor_id, "card.visibility_changed", card["title"], {**meta_base, "from": before.get("visibility", "everyone"), "to": card.get("visibility", "everyone")})
                emitted = True
            if before.get("assignees", []) != card.get("assignees", []):
                self._activity_unlocked(project_id, actor_id, "card.assignees_updated", card["title"], meta_base)
                emitted = True
            if before.get("tags", []) != card.get("tags", []):
                self._activity_unlocked(project_id, actor_id, "card.tags_updated", card["title"], meta_base)
                emitted = True
            if before.get("start") != card.get("start") or before.get("end") != card.get("end"):
                self._activity_unlocked(project_id, actor_id, "card.schedule_updated", card["title"], meta_base)
                emitted = True
            if not emitted:
                self._activity_unlocked(project_id, actor_id, "card.updated", card["title"], meta_base)
            return card

    def delete_card(self, project_id: str, card_id: str, actor_id: str) -> None:
        with self.project_lock(project_id):
            path = self._path(project_id, f"cards/{safe_id(card_id)}.json")
            card = self._read_json(path)
            path.unlink()
            bak = path.with_suffix(path.suffix + ".bak")
            if bak.exists(): bak.unlink()
            self._touch_content_unlocked(project_id)
            self._activity_unlocked(project_id, actor_id, "card.deleted", card["title"], {"card_id": card_id, "visibility": card.get("visibility", "everyone"), "creator_id": card.get("created_by")})

    # ---- Append-only announcement/message utilities ----
    def _materialize_events(self, events: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        items: dict[str, dict[str, Any]] = {}
        order: list[str] = []
        for e in events:
            op = e.get("op", "create")
            if op == "create":
                item = copy.deepcopy(e)
                item["deleted"] = False
                items[e["id"]] = item
                order.append(e["id"])
            elif op == "edit" and e.get("target_id") in items:
                if "body" in e: items[e["target_id"]]["body"] = e.get("body", "")
                if "title" in e: items[e["target_id"]]["title"] = e.get("title", "")
                if "tags" in e: items[e["target_id"]]["tags"] = e.get("tags", [])
                items[e["target_id"]]["edited_at"] = e.get("ts")
            elif op == "delete" and e.get("target_id") in items:
                items[e["target_id"]]["deleted"] = True
                items[e["target_id"]]["deleted_at"] = e.get("ts")
            elif op == "pin" and e.get("target_id") in items:
                items[e["target_id"]]["pinned"] = bool(e.get("pinned"))
        return [items[i] for i in order if i in items]

    def announcements(self, project_id: str) -> list[dict[str, Any]]:
        items = self._materialize_events(self._read_jsonl(self._path(project_id, "announcements.jsonl")))
        items.sort(key=lambda x: (bool(x.get("pinned", False)), x.get("ts", "")), reverse=True)
        return items

    def add_announcement(self, project_id: str, payload: dict[str, Any], actor_id: str) -> dict[str, Any]:
        with self.project_lock(project_id):
            item = {"op": "create", "id": self._new_id("m"), "ts": now_iso(), "actor_id": actor_id, "title": payload.get("title") or "", "body": payload["body"], "tags": payload.get("tags", []), "pinned": False}
            self._append_jsonl(self._path(project_id, "announcements.jsonl"), item)
            self._touch_content_unlocked(project_id)
            self._activity_unlocked(project_id, actor_id, "announcement.created", item["title"] or item["body"][:80])
            return item

    def mutate_announcement(self, project_id: str, msg_id: str, op: str, actor_id: str, body: str | None = None, pinned: bool | None = None, title: str | None = None, tags: list[str] | None = None) -> None:
        safe_id(msg_id, "message id")
        with self.project_lock(project_id):
            e = {"op": op, "id": self._new_id("e"), "target_id": msg_id, "ts": now_iso(), "actor_id": actor_id}
            if body is not None: e["body"] = body
            if title is not None: e["title"] = title
            if tags is not None: e["tags"] = tags
            if pinned is not None: e["pinned"] = pinned
            self._append_jsonl(self._path(project_id, "announcements.jsonl"), e)
            self._touch_content_unlocked(project_id)
            self._activity_unlocked(project_id, actor_id, f"announcement.{op}", msg_id)

    # ---- Discussions ----
    def channels(self, project_id: str) -> list[dict[str, Any]]:
        return self._read_json(self._path(project_id, "discussions/channels.json"), [])

    def create_channel(self, project_id: str, payload: dict[str, Any], actor_id: str) -> dict[str, Any]:
        with self.project_lock(project_id):
            path = self._path(project_id, "discussions/channels.json")
            channels = self._read_json(path, [])
            cid = self._new_id("ch")
            ch = {"id": cid, "name": payload["name"], "visibility": payload.get("visibility", "everyone"), "roles": payload.get("roles", []), "members": payload.get("members", []), "created_at": now_iso(), "created_by": actor_id}
            channels.append(ch)
            self._atomic_write_json(path, channels)
            self._path(project_id, f"discussions/{cid}").mkdir(parents=True, exist_ok=True)
            self._touch_content_unlocked(project_id)
            self._activity_unlocked(project_id, actor_id, "channel.created", ch["name"], {"channel_id": cid})
            return ch

    def update_channel(self, project_id: str, channel_id: str, patch: dict[str, Any], actor_id: str) -> dict[str, Any]:
        with self.project_lock(project_id):
            path = self._path(project_id, "discussions/channels.json")
            channels = self._read_json(path, [])
            target = next((c for c in channels if c["id"] == safe_id(channel_id, "channel id")), None)
            if not target: raise NotFoundError("channel")
            for k in ["name", "visibility", "roles", "members"]:
                if k in patch and patch[k] is not None: target[k] = patch[k]
            self._atomic_write_json(path, channels)
            self._touch_content_unlocked(project_id)
            self._activity_unlocked(project_id, actor_id, "channel.updated", target["name"], {"channel_id": channel_id})
            return target

    def delete_channel(self, project_id: str, channel_id: str, actor_id: str) -> None:
        if channel_id == "general": raise ValidationError("The general channel cannot be deleted")
        with self.project_lock(project_id):
            path = self._path(project_id, "discussions/channels.json")
            channels = self._read_json(path, [])
            target = next((c for c in channels if c["id"] == channel_id), None)
            if not target: raise NotFoundError("channel")
            self._atomic_write_json(path, [c for c in channels if c["id"] != channel_id])
            d = self._path(project_id, f"discussions/{safe_id(channel_id)}")
            if d.exists(): shutil.rmtree(d)
            self._touch_content_unlocked(project_id)
            self._activity_unlocked(project_id, actor_id, "channel.deleted", target["name"], {"channel_id": channel_id})

    def can_view_channel(self, ch: dict[str, Any], person: dict[str, Any]) -> bool:
        v = ch.get("visibility", "everyone")
        if v == "everyone": return True
        if person.get("role") == "owner": return True
        if v == "roles": return person.get("role") in ch.get("roles", [])
        if v == "members": return person.get("id") in ch.get("members", [])
        return False

    def threads(self, project_id: str, channel_id: str) -> list[dict[str, Any]]:
        safe_id(channel_id, "channel id")
        d = self._path(project_id, f"discussions/{channel_id}")
        if not d.exists(): return []
        out = []
        for p in d.glob("thread_*.jsonl"):
            events = self._read_jsonl(p)
            items = self._materialize_events(events)
            if not items: continue
            root = items[0]
            replies = items[1:]
            out.append({"id": p.stem.replace("thread_", ""), "root": root, "reply_count": sum(1 for x in replies if not x.get("deleted")), "last_activity": (events[-1].get("ts") if events else root.get("ts"))})
        out.sort(key=lambda x: x["last_activity"], reverse=True)
        return out

    def create_thread(self, project_id: str, channel_id: str, payload: dict[str, Any], actor_id: str) -> dict[str, Any]:
        safe_id(channel_id, "channel id")
        with self.project_lock(project_id):
            tid = self._new_id("t")
            msg = {"op": "create", "id": self._new_id("m"), "ts": now_iso(), "actor_id": actor_id, "title": payload.get("title") or "", "body": payload["body"], "tags": payload.get("tags", [])}
            self._append_jsonl(self._path(project_id, f"discussions/{channel_id}/thread_{tid}.jsonl"), msg)
            self._touch_content_unlocked(project_id)
            self._activity_unlocked(project_id, actor_id, "thread.created", msg["title"] or msg["body"][:80], {"channel_id": channel_id, "thread_id": tid})
            return {"id": tid, "root": msg, "reply_count": 0, "last_activity": msg["ts"]}

    def thread_messages(self, project_id: str, channel_id: str, thread_id: str) -> list[dict[str, Any]]:
        safe_id(channel_id, "channel id"); safe_id(thread_id, "thread id")
        return self._materialize_events(self._read_jsonl(self._path(project_id, f"discussions/{channel_id}/thread_{thread_id}.jsonl")))

    def reply(self, project_id: str, channel_id: str, thread_id: str, body: str, actor_id: str) -> dict[str, Any]:
        with self.project_lock(project_id):
            path = self._path(project_id, f"discussions/{safe_id(channel_id)}/thread_{safe_id(thread_id)}.jsonl")
            if not path.exists(): raise NotFoundError("thread")
            msg = {"op": "create", "id": self._new_id("m"), "ts": now_iso(), "actor_id": actor_id, "title": "", "body": body, "tags": []}
            self._append_jsonl(path, msg)
            self._touch_content_unlocked(project_id)
            self._activity_unlocked(project_id, actor_id, "reply.created", body[:80], {"thread_id": thread_id})
            return msg

    def mutate_message(self, project_id: str, channel_id: str, thread_id: str, msg_id: str, op: str, actor_id: str, body: str | None = None) -> None:
        with self.project_lock(project_id):
            path = self._path(project_id, f"discussions/{safe_id(channel_id)}/thread_{safe_id(thread_id)}.jsonl")
            if not path.exists(): raise NotFoundError("thread")
            e = {"op": op, "id": self._new_id("e"), "target_id": safe_id(msg_id), "ts": now_iso(), "actor_id": actor_id}
            if body is not None: e["body"] = body
            self._append_jsonl(path, e)
            self._touch_content_unlocked(project_id)
            self._activity_unlocked(project_id, actor_id, f"message.{op}", msg_id)

    # ---- Files ----
    def files(self, project_id: str) -> list[dict[str, Any]]:
        return [x for x in self._read_json(self._path(project_id, "files.json"), []) if not x.get("deleted")]

    def project_size_bytes(self, project_id: str) -> int:
        total = 0
        for p in self.project_root(project_id).rglob("*"):
            if p.is_file() and not p.name.endswith(".lock"):
                try: total += p.stat().st_size
                except OSError: pass
        return total

    def add_file(self, project_id: str, original_name: str, content: bytes, description: str, linked_card_ids: list[str] | None, actor_id: str) -> dict[str, Any]:
        with self.project_lock(project_id):
            linked_card_ids = list(dict.fromkeys(linked_card_ids or []))
            for linked_card_id in linked_card_ids:
                try: self.get_card(project_id, linked_card_id)
                except (NotFoundError, ValueError): raise ValidationError("Linked Card does not exist")
            settings = self.get_settings(project_id)
            quota = int(settings.get("quota_mb", self.settings.default_project_quota_mb)) * 1024 * 1024
            if self.project_size_bytes(project_id) + len(content) > quota:
                raise ValidationError("Project storage quota exceeded")
            fid = self._new_id("f")
            clean = safe_filename(original_name)
            stored = f"{fid}__{clean}"
            path = self._path(project_id, f"files/{stored}")
            with path.open("wb") as fh:
                fh.write(content); fh.flush(); os.fsync(fh.fileno())
            digest = hashlib.sha256(content).hexdigest()
            meta = {"id": fid, "name": clean, "stored_name": stored, "description": description or "", "linked_card_ids": linked_card_ids, "linked_card_id": (linked_card_ids[0] if linked_card_ids else None), "uploader_id": actor_id, "size": len(content), "sha256": digest, "uploaded_at": now_iso(), "deleted": False}
            mpath = self._path(project_id, "files.json")
            items = self._read_json(mpath, [])
            items.append(meta)
            self._atomic_write_json(mpath, items)
            self._touch_content_unlocked(project_id)
            self._activity_unlocked(project_id, actor_id, "file.uploaded", clean, {"file_id": fid})
            return meta

    def file_meta(self, project_id: str, file_id: str) -> dict[str, Any]:
        safe_id(file_id, "file id")
        for f in self.files(project_id):
            if f["id"] == file_id: return f
        raise NotFoundError("file")

    def update_file_meta(self, project_id: str, file_id: str, patch: dict[str, Any], actor_id: str) -> dict[str, Any]:
        with self.project_lock(project_id):
            path = self._path(project_id, "files.json")
            items = self._read_json(path, [])
            target = next((x for x in items if x["id"] == file_id and not x.get("deleted")), None)
            if not target: raise NotFoundError("file")
            for k in ["description", "linked_card_id", "linked_card_ids", "tags"]:
                if k in patch: target[k] = patch[k]
            if "linked_card_ids" in patch:
                target["linked_card_ids"] = list(dict.fromkeys(patch.get("linked_card_ids") or []))
                target["linked_card_id"] = target["linked_card_ids"][0] if target["linked_card_ids"] else None
            elif "linked_card_id" in patch:
                target["linked_card_ids"] = [patch["linked_card_id"]] if patch.get("linked_card_id") else []
            self._atomic_write_json(path, items)
            self._touch_content_unlocked(project_id)
            self._activity_unlocked(project_id, actor_id, "file.updated", target["name"], {"file_id": file_id})
            return target

    def delete_file(self, project_id: str, file_id: str, actor_id: str) -> None:
        with self.project_lock(project_id):
            path = self._path(project_id, "files.json")
            items = self._read_json(path, [])
            target = next((x for x in items if x["id"] == file_id and not x.get("deleted")), None)
            if not target: raise NotFoundError("file")
            target["deleted"] = True; target["deleted_at"] = now_iso(); target["deleted_by"] = actor_id
            self._atomic_write_json(path, items)
            fpath = self._path(project_id, f"files/{target['stored_name']}")
            if fpath.exists(): fpath.unlink()
            self._touch_content_unlocked(project_id)
            self._activity_unlocked(project_id, actor_id, "file.deleted", target["name"], {"file_id": file_id})

    # ---- Search / unread ----
    def search(self, project_id: str, query: str, person: dict[str, Any]) -> dict[str, Any]:
        q = query.casefold().strip()
        result = {"files": [], "threads": []}
        for f in self.files(project_id):
            hay = " ".join([f.get("name", ""), f.get("description", ""), f.get("uploader_id", ""), " ".join(f.get("tags", []))]).casefold()
            if q in hay: result["files"].append(f)
        for ch in self.channels(project_id):
            if not self.can_view_channel(ch, person): continue
            for t in self.threads(project_id, ch["id"]):
                root = t["root"]
                messages = self.thread_messages(project_id, ch["id"], t["id"])
                hay_parts = [root.get("title", ""), " ".join(root.get("tags", []))]
                for msg in messages:
                    if not msg.get("deleted"):
                        hay_parts.extend([msg.get("body", ""), msg.get("actor_id", "")])
                if q in " ".join(hay_parts).casefold():
                    result["threads"].append({**t, "channel_id": ch["id"], "channel_name": ch["name"]})
        return result

    def mark_seen(self, project_id: str, person_id: str, module: str, cursor: str) -> None:
        with self.project_lock(project_id):
            path = self._path(project_id, "people.json")
            people = self._read_json(path, [])
            target = next((p for p in people if p["id"] == person_id), None)
            if not target: raise NotFoundError("person")
            target.setdefault("last_seen", {})[module] = cursor
            self._atomic_write_json(path, people)

    def unread_counts(self, project_id: str, person: dict[str, Any]) -> dict[str, int]:
        seen = person.get("last_seen", {})
        counts = {}
        activity = list(reversed(self.activity_for_person(project_id, person, 10000)))
        mapping = {
            "announcements": ("announcement.",),
            "discussion": ("thread.", "reply.", "message."),
            "cards": ("card.",),
            "files": ("file.",),
            "activity": ("",),
        }
        for module, prefixes in mapping.items():
            cursor = seen.get(module, "")
            counts[module] = sum(1 for a in activity if a.get("ts", "") > cursor and any(a.get("type", "").startswith(p) for p in prefixes))
        return counts

    # ---- Settings/lifecycle ----
    def update_settings(self, project_id: str, patch: dict[str, Any], actor_id: str) -> dict[str, Any]:
        from .security import hash_pin
        with self.project_lock(project_id):
            path = self._path(project_id, "settings.json")
            obj = self._read_json(path)
            expected = patch.pop("expected_version")
            if obj["version"] != expected: raise ConflictError("Settings changed", obj)
            if "expiry" in patch: obj["expiry"] = patch["expiry"]
            if patch.get("quota_mb") is not None: obj["quota_mb"] = patch["quota_mb"]
            if "pin" in patch:
                obj["pin_hash"] = hash_pin(patch["pin"]) if patch.get("pin") else None
            obj["version"] += 1
            self._atomic_write_json(path, obj)
            self._activity_unlocked(project_id, actor_id, "settings.updated", "Project settings")
            return obj

    def close_summary(self, project_id: str) -> dict[str, Any]:
        return {
            "members": len(self.people(project_id)), "cards": len(self.cards(project_id)),
            "announcements": len([x for x in self.announcements(project_id) if not x.get("deleted")]),
            "threads": sum(len(self.threads(project_id, ch["id"])) for ch in self.channels(project_id)),
            "files": len(self.files(project_id)), "size_bytes": self.project_size_bytes(project_id),
        }

    def set_status(self, project_id: str, status: str, actor_id: str) -> dict[str, Any]:
        if status not in {"active", "closing", "archived"}: raise ValidationError("Invalid status")
        with self.project_lock(project_id):
            path = self._path(project_id, "project.json")
            obj = self._read_json(path)
            obj["status"] = status; obj["updated_at"] = now_iso(); obj["version"] += 1
            self._atomic_write_json(path, obj)
            self._activity_unlocked(project_id, actor_id, f"project.{status}", obj["name"])
            return obj

    # ---- Export/import ----
    def _copy_snapshot_unlocked(self, project_id: str, dest: Path) -> None:
        src = self.project_root(project_id)
        def ignore(_dir: str, names: list[str]) -> set[str]:
            return {n for n in names if n.endswith(".lock") or n.endswith(".tmp") or n.endswith(".bak") or n == ".card-create-idempotency.json"}
        shutil.copytree(src, dest, ignore=ignore)

    @staticmethod
    def _sha256_file(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                h.update(chunk)
        return h.hexdigest()

    def export_project(self, project_id: str) -> tuple[Path, dict[str, Any]]:
        project = self.get_project(project_id)
        with tempfile.TemporaryDirectory(prefix="popup_snapshot_") as td:
            tdpath = Path(td)
            snapshot = tdpath / "snapshot"
            with self.project_lock(project_id):
                self._copy_snapshot_unlocked(project_id, snapshot)
            packroot = tdpath / "pack"
            data_dir = packroot / "data"; readable = packroot / "readable"; files_out = packroot / "files"
            data_dir.mkdir(parents=True); readable.mkdir(parents=True); files_out.mkdir(parents=True)
            for p in snapshot.iterdir():
                if p.name == "files":
                    for fp in p.iterdir():
                        if fp.is_file(): shutil.copy2(fp, files_out / fp.name)
                else:
                    dest = data_dir / p.name
                    if p.is_dir(): shutil.copytree(p, dest)
                    else: shutil.copy2(p, dest)
            self._write_readable(snapshot, readable)
            checksums: dict[str, str] = {}
            for p in sorted(packroot.rglob("*")):
                if p.is_file(): checksums[p.relative_to(packroot).as_posix()] = self._sha256_file(p)
            pack_manifest = {
                "format": FORMAT_NAME, "format_version": FORMAT_VERSION, "project_id": project_id,
                "project_name": project["name"], "exported_at": now_iso(), "source_instance_id": self.settings.instance_id,
                "canonical": False, "checksums": checksums,
            }
            self._atomic_write_json(packroot / "pack_manifest.json", pack_manifest)
            out_dir = self.root / ".exports"; out_dir.mkdir(exist_ok=True)
            safe_name = safe_filename(project["name"]).replace(" ", "_") or project_id
            out = out_dir / f"{safe_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for p in sorted(packroot.rglob("*")):
                    if p.is_file(): zf.write(p, p.relative_to(packroot).as_posix())
            digest = self._sha256_file(out)
        # Record export without changing content_updated_at.
        with self.project_lock(project_id):
            path = self._path(project_id, "project.json")
            p = self._read_json(path); p["last_export_at"] = pack_manifest["exported_at"]; p["last_export_digest"] = digest
            self._atomic_write_json(path, p)
            self._activity_unlocked(project_id, "system", "project.exported", out.name, {"sha256": digest})
        return out, {**pack_manifest, "zip_sha256": digest}

    def _write_readable(self, snapshot: Path, readable: Path) -> None:
        project = self._read_json(snapshot / "project.json")
        people = self._read_json(snapshot / "people.json", [])
        cards = []
        for p in sorted((snapshot / "cards").glob("c_*.json")):
            if not p.name.endswith(".bak"): cards.append(self._read_json(p))
        files = self._read_json(snapshot / "files.json", [])
        announcements = self._materialize_events(self._read_jsonl(snapshot / "announcements.jsonl"))
        overview = [f"{project['name']}", "=" * len(project['name']), "", project.get("description", ""), "", f"Status: {project.get('status')}", f"Created: {project.get('created_at')}", f"Expiry: {project.get('expiry') or '—'}", "", "Members:"]
        overview += [f"- {p['display_name']} ({p['role']})" for p in people]
        (readable / "overview.txt").write_text("\n".join(overview) + "\n", "utf-8")
        card_lines = []
        note_lines = []
        for c in cards:
            lines = [f"[{c.get('status','')}] {c['title']} ({c.get('type','task')})", f"Updated: {c.get('updated_at','')}", f"Tags: {', '.join(c.get('tags', [])) or '—'}", c.get("content", ""), "", "---", ""]
            if c.get("type") == "note":
                note_lines += lines
            else:
                card_lines += lines
        # Keep the legacy tasks-and-events filename for pack 1.0 readers; Notes
        # are canonical Card JSON and also receive their own readable export.
        (readable / "tasks-and-events.txt").write_text("\n".join(card_lines), "utf-8")
        (readable / "notes.txt").write_text("\n".join(note_lines), "utf-8")
        ann_lines = []
        for a in announcements:
            if a.get("deleted"): continue
            ann_lines += [f"{a.get('title') or '(Announcement)'} — {a.get('ts','')}", a.get("body", ""), "", "---", ""]
        (readable / "announcements.txt").write_text("\n".join(ann_lines), "utf-8")
        f_lines = [f"{f.get('name')} | {f.get('size',0)} bytes | {f.get('description','')}" for f in files if not f.get("deleted")]
        (readable / "files-index.txt").write_text("\n".join(f_lines) + "\n", "utf-8")
        dr = readable / "discussions"; dr.mkdir(exist_ok=True)
        channels = self._read_json(snapshot / "discussions/channels.json", [])
        for ch in channels:
            lines = [f"#{ch['name']}", "=" * (len(ch['name']) + 1), ""]
            d = snapshot / "discussions" / ch["id"]
            if d.exists():
                for tf in sorted(d.glob("thread_*.jsonl")):
                    msgs = self._materialize_events(self._read_jsonl(tf))
                    for i, m in enumerate(msgs):
                        if m.get("deleted"): continue
                        prefix = "THREAD" if i == 0 else "REPLY"
                        lines += [f"{prefix} {m.get('title','')} [{m.get('ts','')}] actor={m.get('actor_id','')}", m.get("body", ""), ""]
                    lines += ["---", ""]
            (dr / f"{safe_filename(ch['name'])}.txt").write_text("\n".join(lines), "utf-8")

    def export_workspace_bundle(self, project_ids: list[str]) -> tuple[Path, dict[str, Any]]:
        ids = list(dict.fromkeys(project_ids))
        if not ids:
            raise ValidationError("No accessible projects to export")
        with tempfile.TemporaryDirectory(prefix="cocklebur_workspace_") as td:
            root = Path(td) / "workspace"
            root.mkdir(parents=True)
            projects_dir = root / "projects"
            projects_dir.mkdir()
            items: list[dict[str, Any]] = []
            checksums: dict[str, str] = {}
            for pid in ids:
                if not self.exists(pid):
                    raise NotFoundError("project")
                pack, meta = self.export_project(pid)
                target = projects_dir / f"{pid}.zip"
                shutil.copy2(pack, target)
                pack.unlink(missing_ok=True)
                rel = target.relative_to(root).as_posix()
                digest = self._sha256_file(target)
                checksums[rel] = digest
                items.append({"project_id": pid, "project_name": meta.get("project_name"), "file": rel, "sha256": digest})
            manifest = {
                "format": "cocklebur-workspace-bundle",
                "format_version": "1.0",
                "exported_at": now_iso(),
                "source_instance_id": self.settings.instance_id,
                "projects": items,
            }
            self._atomic_write_json(root / "bundle-manifest.json", manifest)
            self._atomic_write_json(root / "checksums.json", checksums)
            out_dir = self.root / ".exports"
            out_dir.mkdir(exist_ok=True)
            out = out_dir / f"Cocklebur_Workspace_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
            with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for f in sorted(root.rglob("*")):
                    if f.is_file():
                        zf.write(f, f.relative_to(root).as_posix())
            digest = self._sha256_file(out)
        return out, {**manifest, "checksums": checksums, "zip_sha256": digest}

    def _safe_extract_zip(self, zip_path: Path, dest: Path, max_bytes: int | None = None) -> None:
        if not zipfile.is_zipfile(zip_path):
            raise ValidationError("Not a valid ZIP")
        limit = max_bytes if max_bytes is not None else self.settings.max_import_mb * 1024 * 1024
        with zipfile.ZipFile(zip_path) as zf:
            total_uncompressed = sum(info.file_size for info in zf.infolist())
            if total_uncompressed > limit:
                raise ValidationError("Archive expands beyond the configured limit")
            for info in zf.infolist():
                name = info.filename
                if name.startswith(("/", "\\")) or ".." in Path(name).parts:
                    raise ValidationError("Unsafe ZIP path")
                target = (dest / name).resolve()
                if dest.resolve() not in target.parents and target != dest.resolve():
                    raise ValidationError("Unsafe ZIP path")
            zf.extractall(dest)

    def unpack_workspace_bundle(self, zip_path: Path, dest: Path) -> list[Path]:
        self._safe_extract_zip(zip_path, dest)
        manifest_path = dest / "bundle-manifest.json"
        if not manifest_path.exists():
            return [zip_path]
        manifest = self._read_json(manifest_path)
        if manifest.get("format") != "cocklebur-workspace-bundle" or manifest.get("format_version") != "1.0":
            raise ValidationError("Unsupported Workspace Bundle")
        checksum_path = dest / "checksums.json"
        checksums = self._read_json(checksum_path, {}) if checksum_path.exists() else {}
        packs: list[Path] = []
        for item in manifest.get("projects", []):
            rel = item.get("file", "")
            path = (dest / rel).resolve()
            if dest.resolve() not in path.parents or not path.is_file():
                raise ValidationError("Invalid bundle project path")
            expected = item.get("sha256") or checksums.get(rel)
            if expected and self._sha256_file(path) != expected:
                raise ValidationError(f"Workspace checksum mismatch: {rel}")
            self.validate_pack(path)
            packs.append(path)
        if not packs:
            raise ValidationError("Workspace Bundle contains no projects")
        return packs

    def preflight_pack(self, zip_path: Path) -> dict[str, Any]:
        try:
            manifest = self.validate_pack(zip_path)
            pid = manifest.get("project_id")
            status = "Duplicate ID" if pid and self.exists(pid) else "Ready"
            return {"status": status, "project_id": pid, "project_name": manifest.get("project_name"), "format_version": manifest.get("format_version")}
        except ValidationError as exc:
            msg = str(exc)
            status = "Incompatible version" if "version" in msg.lower() else "Invalid pack"
            return {"status": status, "detail": msg}

    def validate_pack(self, zip_path: Path) -> dict[str, Any]:
        if not zipfile.is_zipfile(zip_path): raise ValidationError("Not a valid ZIP")
        with tempfile.TemporaryDirectory(prefix="popup_validate_") as td:
            dest = Path(td)
            with zipfile.ZipFile(zip_path) as zf:
                total_uncompressed = sum(info.file_size for info in zf.infolist())
                if total_uncompressed > self.settings.max_import_mb * 1024 * 1024:
                    raise ValidationError("Pack expands beyond the configured import limit")
                for info in zf.infolist():
                    name = info.filename
                    if name.startswith(("/", "\\")) or ".." in Path(name).parts:
                        raise ValidationError("Unsafe ZIP path")
                    target = (dest / name).resolve()
                    if dest.resolve() not in target.parents and target != dest.resolve():
                        raise ValidationError("Unsafe ZIP path")
                zf.extractall(dest)
            manifest = self._read_json(dest / "pack_manifest.json")
            if manifest.get("format") != FORMAT_NAME: raise ValidationError("Unsupported pack format")
            if manifest.get("format_version") != FORMAT_VERSION: raise ValidationError(f"Unsupported format version {manifest.get('format_version')}")
            for rel, expected in manifest.get("checksums", {}).items():
                p = dest / rel
                if not p.exists() or self._sha256_file(p) != expected: raise ValidationError(f"Checksum mismatch: {rel}")
            required = ["data/project.json", "data/manifest.json", "data/people.json", "data/settings.json"]
            for rel in required:
                if not (dest / rel).exists(): raise ValidationError(f"Missing {rel}")
            return manifest

    def import_project(self, zip_path: Path, allow_new_id_on_conflict: bool = False, target_mode: str | None = None) -> dict[str, Any]:
        manifest = self.validate_pack(zip_path)
        with tempfile.TemporaryDirectory(prefix="popup_import_") as td:
            dest = Path(td)
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(dest)
            project = self._read_json(dest / "data/project.json")
            original_id = project["id"]
            project_id = original_id
            if self.exists(project_id):
                if not allow_new_id_on_conflict:
                    raise ConflictError("A project with this ID already exists", self.get_project(project_id))
                project_id = self._new_id("p")
                project["id"] = project_id
            root = self.project_root(project_id)
            if root.exists():
                shutil.rmtree(root)
            root.mkdir(parents=True)
            for p in (dest / "data").iterdir():
                target = root / p.name
                if p.name == "project.json":
                    continue
                if p.is_dir():
                    shutil.copytree(p, target)
                else:
                    shutil.copy2(p, target)
            files_src = dest / "files"
            files_dst = root / "files"
            files_dst.mkdir(exist_ok=True)
            if files_src.exists():
                for p in files_src.iterdir():
                    if p.is_file():
                        shutil.copy2(p, files_dst / p.name)
            project["canonical_instance_id"] = self.settings.instance_id
            project["source_snapshot_instance_id"] = manifest.get("source_instance_id")
            if target_mode in {"local", "server"}:
                project["mode"] = target_mode
            project["status"] = "active"
            project["updated_at"] = now_iso()
            project["content_updated_at"] = now_iso()
            project["version"] = int(project.get("version", 0)) + 1
            self._atomic_write_json(root / "project.json", project)

            # Compatibility normalization for older packs.
            people_path = root / "people.json"
            people = self._read_json(people_path, [])
            for person in people:
                person.setdefault("role", "member")
                person.setdefault("access_hashes", [])
                person.setdefault("last_seen", {})
                person.pop("recovery_hash", None)
            owners = [p for p in people if p.get("role") == "owner"]
            if not owners:
                imported_owner = {
                    "id": self._new_id("u"),
                    "display_name": "Imported Owner",
                    "role": "owner",
                    "joined_at": now_iso(),
                    "access_hashes": [],
                    "last_seen": {},
                }
                people.insert(0, imported_owner)
                owners = [imported_owner]
            primary_owner_id = owners[0]["id"]
            if project.get("mode") == "server":
                for person in people:
                    person["access_hashes"] = []
            self._atomic_write_json(people_path, people)

            cards_dir = root / "cards"
            cards_dir.mkdir(exist_ok=True)
            for card_path in cards_dir.glob("c_*.json"):
                if card_path.name.endswith(".bak"):
                    continue
                card = self._read_json(card_path)
                changed = False
                if not card.get("created_by"):
                    card["created_by"] = primary_owner_id
                    changed = True
                if not card.get("updated_by"):
                    card["updated_by"] = card["created_by"]
                    changed = True
                if card.get("edit_access") not in {"public", "private"}:
                    card["edit_access"] = "public"
                    changed = True
                if card.get("visibility") not in {"everyone", "private"}:
                    card["visibility"] = "everyone"
                    changed = True
                before_normalized = copy.deepcopy(card)
                self._normalize_card_fields(card)
                if card != before_normalized:
                    changed = True
                if changed:
                    self._atomic_write_json(card_path, card)

            self._activity_unlocked(project_id, "system", "project.imported", project["name"], {"source_instance_id": manifest.get("source_instance_id")})
            return project

    def can_delete_after_export(self, project_id: str) -> bool:
        p = self.get_project(project_id)
        return bool(p.get("last_export_at") and p["last_export_at"] >= p.get("content_updated_at", ""))

    def delete_project(self, project_id: str, require_export: bool = True) -> None:
        if require_export and not self.can_delete_after_export(project_id):
            raise ValidationError("Export the current project state before deleting")
        root = self.project_root(project_id)
        if not root.exists(): raise NotFoundError("project")
        shutil.rmtree(root)
        self._unregister_root(project_id)
