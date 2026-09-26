from __future__ import annotations

import io
import json
import secrets
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import qrcode
from fastapi import Body, Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse
from starlette.background import BackgroundTask
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import __version__
from .config import load_settings
from .models import (
    CardCreate, CardPatch, ChannelCreate, JoinRequest, MessageCreate, MessageEdit, AnnouncementEdit,
    PersonPatch, ProjectCreate, ProjectPatch, ReplyCreate, SeenUpdate, SettingsPatch, SelfPatch, HostClaim, HostRecover, InstancePermissionPatch, OwnerRecover, WorkspaceImportCommit,
)
from .rendering import render_markdown
from .security import safe_id
from .storage import CapsuleStore, ConflictError, NotFoundError, PermissionError_, ValidationError
from .update_center import UpdateCenter

settings = load_settings()
store = CapsuleStore(settings)
update_center = UpdateCenter(settings, store)
app = FastAPI(title="Cocklebur", version=__version__)
BASE = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE / "static"), name="static")
templates = Jinja2Templates(directory=BASE / "templates")


def cookie_name(project_id: str) -> str:
    return f"pw_{safe_id(project_id).replace('-', '_')}"


def set_access_cookie(response: Response, project_id: str, token: str) -> None:
    response.set_cookie(
        cookie_name(project_id), token, httponly=True, secure=settings.base_url.startswith("https://"),
        samesite="lax", max_age=60 * 60 * 24 * 180, path="/",
    )


HOST_COOKIE = "cocklebur_host"

def is_host(request: Request) -> bool:
    if settings.app_mode != "server":
        return True
    return bool(store.resolve_host(request.cookies.get(HOST_COOKIE)))

def require_host(request: Request) -> None:
    if settings.app_mode == "server" and not is_host(request):
        raise HTTPException(403, "Instance Host access is required")

def set_host_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        HOST_COOKIE, token, httponly=True, secure=settings.base_url.startswith("https://"),
        samesite="lax", max_age=60 * 60 * 24 * 180, path="/",
    )

def _delegated_instance_access(request: Request) -> dict[str, Any]:
    result = {"can_create_projects": False, "can_import_projects": False, "sources": []}
    for grant in store.instance_grants():
        project_id = str(grant.get("project_id") or "")
        person_id = str(grant.get("person_id") or "")
        if not project_id or not person_id:
            continue
        try:
            person = store.resolve_access(project_id, request.cookies.get(cookie_name(project_id)))
        except (NotFoundError, ValueError, ValidationError):
            continue
        if not person or person.get("id") != person_id:
            continue
        can_create = bool(grant.get("can_create_projects"))
        can_import = bool(grant.get("can_import_projects"))
        result["can_create_projects"] = result["can_create_projects"] or can_create
        result["can_import_projects"] = result["can_import_projects"] or can_import
        result["sources"].append({
            "project_id": project_id,
            "person_id": person_id,
            "display_name": person.get("display_name", person_id),
            "can_create_projects": can_create,
            "can_import_projects": can_import,
        })
    return result

def instance_access(request: Request) -> dict[str, Any]:
    if settings.app_mode != "server":
        return {
            "mode": settings.app_mode, "host": True, "host_claimed": True,
            "can_create_projects": True, "can_import_projects": True, "sources": [],
        }
    host = is_host(request)
    delegated = _delegated_instance_access(request)
    return {
        "mode": settings.app_mode,
        "host": host,
        "host_claimed": store.host_claimed(),
        "can_create_projects": host or delegated["can_create_projects"],
        "can_import_projects": host or delegated["can_import_projects"],
        "sources": delegated["sources"],
    }

def require_instance_permission(request: Request, permission: str) -> None:
    access = instance_access(request)
    key = "can_create_projects" if permission == "create" else "can_import_projects"
    if not access.get(key):
        label = "create projects" if permission == "create" else "import project packs"
        raise HTTPException(403, f"Instance permission is required to {label}")


def current_person(request: Request, project_id: str) -> dict[str, Any]:
    try:
        p = store.resolve_access(project_id, request.cookies.get(cookie_name(project_id)))
    except (NotFoundError, ValueError):
        raise HTTPException(404, "Project not found")
    if not p:
        raise HTTPException(401, "Join or recover access to this project")
    return p


def require(project_id: str, request: Request, roles: set[str] | None = None) -> dict[str, Any]:
    p = current_person(request, project_id)
    if roles and p.get("role") not in roles:
        raise HTTPException(403, "Insufficient permission")
    return p


def get_channel_for_person(project_id: str, channel_id: str, person: dict[str, Any]) -> dict[str, Any]:
    channel = next((c for c in store.channels(project_id) if c["id"] == channel_id), None)
    if not channel:
        raise HTTPException(404, "Channel not found")
    if not store.can_view_channel(channel, person):
        raise HTTPException(403, "Channel is not visible to you")
    return channel


@app.exception_handler(ConflictError)
def conflict_handler(_request: Request, exc: ConflictError):
    return JSONResponse(status_code=409, content={"detail": str(exc), "current": exc.current})


@app.exception_handler(ValidationError)
def validation_handler(_request: Request, exc: ValidationError):
    return JSONResponse(status_code=400, content={"detail": str(exc)})


@app.exception_handler(NotFoundError)
def notfound_handler(_request: Request, exc: NotFoundError):
    return JSONResponse(status_code=404, content={"detail": str(exc)})


@app.exception_handler(PermissionError_)
def permission_handler(_request: Request, exc: PermissionError_):
    return JSONResponse(status_code=403, content={"detail": str(exc)})


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    response.headers.setdefault("Permissions-Policy", "camera=(self), microphone=(), geolocation=()")
    response.headers.setdefault("Cache-Control", "no-store")
    return response


@app.get("/health")
def health():
    return {
        "status": "ok", "version": __version__, "mode": settings.app_mode,
        "instance_id": settings.instance_id,
        "host_claimed": store.host_claimed() if settings.app_mode == "server" else True,
    }


@app.get("/api/host/status")
def host_status(request: Request):
    access = instance_access(request)
    host = store.resolve_host(request.cookies.get(HOST_COOKIE)) if settings.app_mode == "server" else {"display_name": "Local Host"}
    return {**access, "host_profile": host}


@app.get("/api/instance/access")
def get_instance_access(request: Request):
    return instance_access(request)


@app.get("/api/update/status")
def update_status(request: Request):
    require_host(request)
    return update_center.status()


@app.post("/api/update/stage")
async def update_stage(request: Request, file: UploadFile = File(...)):
    require_host(request)
    max_bytes = settings.max_update_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(413, "Update package exceeds upload limit")
    temp = settings.data_dir / ".imports"
    temp.mkdir(exist_ok=True)
    path = temp / f"update_{datetime.now().timestamp()}_{secrets.token_hex(4)}.zip"
    path.write_bytes(data)
    try:
        return update_center.stage(path, file.filename or "update.zip")
    finally:
        path.unlink(missing_ok=True)


@app.delete("/api/update/staged")
def update_cancel(request: Request):
    require_host(request)
    return update_center.cancel()


@app.post("/api/host/claim")
def host_claim(payload: HostClaim):
    if settings.app_mode != "server":
        return {"ok": True, "host": True, "host_claimed": True}
    if store.host_claimed():
        raise HTTPException(409, "This Cocklebur instance already has a Host. Use Host recovery on a new browser.")
    if not settings.bootstrap_key or not secrets.compare_digest(payload.key, settings.bootstrap_key):
        raise HTTPException(403, "Invalid Host bootstrap key")
    host, access, recovery = store.claim_host(payload.display_name)
    r = JSONResponse({"ok": True, "host": True, "host_claimed": True, "host_profile": host, "host_recovery_code": recovery})
    set_host_cookie(r, access)
    return r


@app.post("/api/host/recover")
def host_recover(payload: HostRecover):
    if settings.app_mode != "server":
        return {"ok": True, "host": True}
    host, access, recovery = store.recover_host(payload.code)
    r = JSONResponse({"ok": True, "host": True, "host_claimed": True, "host_profile": host, "host_recovery_code": recovery})
    set_host_cookie(r, access)
    return r


@app.post("/api/host/recovery/rotate")
def rotate_host_recovery(request: Request):
    require_host(request)
    return {"host_recovery_code": store.rotate_host_recovery()}


@app.post("/api/host/logout")
def host_logout():
    r = JSONResponse({"ok": True})
    r.delete_cookie(HOST_COOKIE, path="/")
    return r


@app.get("/api/instance/people")
def instance_people(request: Request):
    require_host(request)
    return store.instance_people_catalog()


@app.patch("/api/instance/people/{project_id}/{person_id}/permissions")
def patch_instance_permissions(project_id: str, person_id: str, payload: InstancePermissionPatch, request: Request):
    require_host(request)
    return store.set_instance_permissions(
        project_id, person_id,
        can_create_projects=payload.can_create_projects,
        can_import_projects=payload.can_import_projects,
    )


@app.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {"mode": settings.app_mode, "version": __version__})


@app.get("/project/{project_id}", response_class=HTMLResponse)
def project_page(request: Request, project_id: str):
    project = store.get_project(project_id)
    person = store.resolve_access(project_id, request.cookies.get(cookie_name(project_id)))
    if project.get("mode") == "server" and not person:
        return templates.TemplateResponse(request, "locked.html", {"project": project, "version": __version__})
    return templates.TemplateResponse(request, "project.html", {"project": project, "person": person, "version": __version__})


@app.get("/join/{project_id}", response_class=HTMLResponse)
def join_page(request: Request, project_id: str, token: str = ""):
    project = store.get_project(project_id)
    return templates.TemplateResponse(request, "join.html", {"project": project, "token": token, "version": __version__})


@app.get("/recover/{project_id}", response_class=HTMLResponse)
def recover_page(request: Request, project_id: str, token: str = ""):
    project = store.get_project(project_id)
    # Recovery links are intentionally GET-safe. Link previews, scanners, browser
    # prefetch, and ngrok interstitials must never consume a one-time token.
    return templates.TemplateResponse(request, "recover.html", {
        "project": project, "token": token, "version": __version__, "error": None,
    })


@app.post("/recover/{project_id}", response_class=HTMLResponse)
def recover_exchange(request: Request, project_id: str, token: str = Form(...)):
    project = store.get_project(project_id)
    try:
        person, access = store.exchange_recovery(project_id, token)
    except PermissionError_ as exc:
        return templates.TemplateResponse(request, "recover.html", {
            "project": project, "token": "", "version": __version__, "error": str(exc),
        }, status_code=403)
    r = RedirectResponse(f"/project/{project_id}", status_code=303)
    set_access_cookie(r, project_id, access)
    return r


@app.post("/api/projects/{project_id}/owner-recover")
def owner_recover(project_id: str, payload: OwnerRecover, request: Request):
    existing = store.resolve_access(project_id, request.cookies.get(cookie_name(project_id)))
    if existing:
        role = str(existing.get("role") or "member").capitalize()
        name = str(existing.get("display_name") or "this user")
        raise HTTPException(409, f"This browser already has project access as {name} ({role}). Owner recovery is only for a browser with no project session.")
    person, access, next_code = store.recover_owner_code(project_id, payload.code)
    r = JSONResponse({
        "person": {"id": person["id"], "display_name": person["display_name"], "role": person["role"]},
        "owner_recovery_code": next_code,
    })
    if access:
        set_access_cookie(r, project_id, access)
    return r


@app.get("/api/local/projects")
def local_projects():
    if settings.app_mode != "local":
        raise HTTPException(404)
    return store.list_local_projects()


@app.post("/api/projects")
def create_project(payload: ProjectCreate, request: Request, response: Response):
    if settings.app_mode == "server":
        require_instance_permission(request, "create")
    data = payload.model_dump()
    if settings.app_mode == "server":
        data["mode"] = "server"
        data["storage_path"] = None
    p, owner_token, owner_recovery_code = store.create_project(data)
    if owner_token:
        set_access_cookie(response, p["id"], owner_token)
    return {**p, "owner_recovery_code": owner_recovery_code}


@app.post("/api/projects/import")
async def import_project(request: Request, response: Response, file: UploadFile = File(...), allow_new_id_on_conflict: bool = Form(False)):
    if settings.app_mode == "server":
        require_instance_permission(request, "import")
    max_bytes = settings.max_import_mb * 1024 * 1024
    data = await file.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(413, "Import exceeds upload limit")
    temp = settings.data_dir / ".imports"
    temp.mkdir(exist_ok=True)
    path = temp / f"import_{datetime.now().timestamp()}.zip"
    path.write_bytes(data)
    try:
        project = store.import_project(path, allow_new_id_on_conflict=allow_new_id_on_conflict, target_mode=settings.app_mode)
        result = dict(project)
        owners = [p for p in store.people(project["id"]) if p.get("role") == "owner"]
        if not owners:
            raise ValidationError("Imported project has no Owner")
        owner = owners[0]
        owner_recovery_code = store.rotate_owner_recovery(project["id"], owner["id"], "system")
        result["owner_recovery_code"] = owner_recovery_code
        if project.get("mode") == "server":
            access = store.issue_access(project["id"], owner["id"], "system")
            set_access_cookie(response, project["id"], access)
            result["owner_access_ready"] = True
        return result
    finally:
        path.unlink(missing_ok=True)


def _exportable_project_ids(request: Request) -> list[str]:
    if settings.app_mode == "local":
        return [p["id"] for p in store.list_local_projects()]
    ids: list[str] = []
    for pid in store.list_project_ids():
        try:
            person = store.resolve_access(pid, request.cookies.get(cookie_name(pid)))
        except Exception:
            person = None
        if person and person.get("role") in {"owner", "member"}:
            ids.append(pid)
    return ids


@app.get("/api/projects/export-bundle")
def export_workspace_bundle(request: Request):
    ids = _exportable_project_ids(request)
    if not ids:
        raise HTTPException(400, "No accessible Owner/Member projects to export")
    path, _meta = store.export_workspace_bundle(ids)
    return FileResponse(path, filename=path.name, media_type="application/zip", background=BackgroundTask(path.unlink, missing_ok=True))


@app.post("/api/projects/import/preflight")
async def import_preflight(request: Request, files: list[UploadFile] = File(...)):
    if settings.app_mode == "server":
        require_instance_permission(request, "import")
    if not files:
        raise HTTPException(400, "Choose at least one project pack or Workspace Bundle")
    imports_root = settings.data_dir / ".imports"
    imports_root.mkdir(exist_ok=True)
    cutoff = datetime.now().timestamp() - 24 * 60 * 60
    for stale in imports_root.glob("batch_*"):
        try:
            if stale.is_dir() and stale.stat().st_mtime < cutoff:
                shutil.rmtree(stale, ignore_errors=True)
        except OSError:
            pass
    batch_id = "batch_" + secrets.token_hex(8)
    batch_root = imports_root / batch_id
    batch_root.mkdir(parents=True, exist_ok=False)
    entries: list[dict[str, Any]] = []
    try:
        for upload_index, upload in enumerate(files):
            data = await upload.read(settings.max_import_mb * 1024 * 1024 + 1)
            if len(data) > settings.max_import_mb * 1024 * 1024:
                entries.append({"item_id": f"item_{len(entries)}", "status": "Invalid pack", "detail": "Import exceeds configured limit", "source_name": upload.filename})
                continue
            src = batch_root / f"source_{upload_index}.zip"
            src.write_bytes(data)
            extract = batch_root / f"extract_{upload_index}"
            extract.mkdir()
            try:
                packs = store.unpack_workspace_bundle(src, extract)
                for pack in packs:
                    item_id = f"item_{len(entries)}"
                    target = batch_root / f"{item_id}.zip"
                    shutil.copy2(pack, target)
                    pre = store.preflight_pack(target)
                    entries.append({**pre, "item_id": item_id, "file": target.name, "source_name": upload.filename})
            except Exception as exc:
                entries.append({"item_id": f"item_{len(entries)}", "status": "Invalid pack", "detail": str(exc), "source_name": upload.filename})
        (batch_root / "batch.json").write_text(json.dumps({"batch_id": batch_id, "entries": entries}, ensure_ascii=False, indent=2), "utf-8")
        return {"batch_id": batch_id, "entries": entries}
    except Exception:
        shutil.rmtree(batch_root, ignore_errors=True)
        raise


@app.post("/api/projects/import/commit")
def import_commit(payload: WorkspaceImportCommit, request: Request, response: Response):
    if settings.app_mode == "server":
        require_instance_permission(request, "import")
    imports_root = (settings.data_dir / ".imports").resolve()
    batch_root = (imports_root / payload.batch_id).resolve()
    if imports_root not in batch_root.parents or not (batch_root / "batch.json").exists():
        raise HTTPException(404, "Import batch not found")
    data = json.loads((batch_root / "batch.json").read_text("utf-8"))
    results: list[dict[str, Any]] = []
    try:
        for entry in data.get("entries", []):
            if entry.get("status") not in {"Ready", "Duplicate ID"}:
                results.append({**entry, "result": "skipped"})
                continue
            if entry.get("status") == "Duplicate ID" and payload.duplicate_policy == "skip":
                results.append({**entry, "result": "skipped"})
                continue
            pack = batch_root / entry["file"]
            project = store.import_project(pack, allow_new_id_on_conflict=(payload.duplicate_policy == "new_id"), target_mode=settings.app_mode)
            owners = [person for person in store.people(project["id"]) if person.get("role") == "owner"]
            recovery = None
            if owners:
                owner = owners[0]
                recovery = store.rotate_owner_recovery(project["id"], owner["id"], "system")
                if project.get("mode") == "server":
                    access = store.issue_access(project["id"], owner["id"], "system")
                    set_access_cookie(response, project["id"], access)
            results.append({**entry, "result": "imported", "imported_project_id": project["id"], "owner_recovery_code": recovery})
        return {"results": results}
    finally:
        shutil.rmtree(batch_root, ignore_errors=True)


@app.get("/api/projects/{project_id}")
def get_project(project_id: str, request: Request):
    person = require(project_id, request)
    p = store.get_project(project_id)
    result = {**p, "me": {"id": person["id"], "display_name": person["display_name"], "role": person["role"]}}
    if settings.app_mode == "local" and p.get("mode") == "local":
        result["storage_path"] = str(store.project_root(project_id).resolve())
    return result


@app.get("/api/projects/{project_id}/summary")
def summary(project_id: str, request: Request):
    person = require(project_id, request)
    p = store.get_project(project_id)
    return {"id": p["id"], "name": p["name"], "description": p.get("description", ""), "status": p["status"], "expiry": p.get("expiry"), "content_updated_at": p.get("content_updated_at"), "role": person["role"], "unread": store.unread_counts(project_id, person)}


@app.patch("/api/projects/{project_id}")
def patch_project(project_id: str, payload: ProjectPatch, request: Request):
    person = require(project_id, request, {"owner"})
    return store.update_project(project_id, payload.model_dump(exclude_unset=True), person["id"])


@app.get("/api/projects/{project_id}/me")
def me(project_id: str, request: Request):
    p = require(project_id, request)
    return {k: p.get(k) for k in ["id", "display_name", "role", "joined_at", "last_seen"]}


@app.patch("/api/projects/{project_id}/me")
def patch_me(project_id: str, payload: SelfPatch, request: Request):
    actor = require(project_id, request)
    updated = store.update_person(project_id, actor["id"], {"display_name": payload.display_name}, actor["id"])
    return {k: updated.get(k) for k in ["id", "display_name", "role", "joined_at"]}


@app.post("/api/projects/{project_id}/me/owner-recovery/rotate")
def rotate_my_owner_recovery(project_id: str, request: Request):
    actor = require(project_id, request, {"owner"})
    code = store.rotate_owner_recovery(project_id, actor["id"], actor["id"])
    return {"owner_recovery_code": code}


# Invite/member
@app.get("/api/projects/{project_id}/invite")
def invite_info(project_id: str, request: Request):
    require(project_id, request, {"owner"})
    s = store.get_settings(project_id)
    return {"enabled": bool(s.get("invite_hash")), "pin_enabled": bool(s.get("pin_hash")), "invite_created_at": s.get("invite_created_at")}


@app.post("/api/projects/{project_id}/invite/regenerate")
def regenerate_invite(project_id: str, request: Request, pin: str | None = Body(default=None, embed=True)):
    person = require(project_id, request, {"owner"})
    token = store.make_invite(project_id, person["id"], pin)
    url = f"{settings.base_url}/join/{project_id}?token={token}"
    return {"invite_url": url, "token": token, "pin_enabled": bool(pin)}


@app.get("/api/projects/{project_id}/invite/qr")
def invite_qr(project_id: str, request: Request, token: str):
    require(project_id, request, {"owner"})
    s = store.get_settings(project_id)
    from .security import verify_token
    if not s.get("invite_hash") or not verify_token(token, s["invite_hash"]):
        raise HTTPException(400, "Token no longer matches the active invite")
    url = f"{settings.base_url}/join/{project_id}?token={token}"
    img = qrcode.make(url)
    buf = io.BytesIO(); img.save(buf, format="PNG"); buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")


@app.post("/api/projects/{project_id}/join")
def join_project(project_id: str, payload: JoinRequest):
    person, token = store.join(project_id, payload.display_name, payload.token, payload.pin)
    r = JSONResponse({"person": {"id": person["id"], "display_name": person["display_name"], "role": person["role"]}})
    set_access_cookie(r, project_id, token)
    return r


@app.get("/api/projects/{project_id}/people")
def people(project_id: str, request: Request):
    require(project_id, request)
    return [{k: p.get(k) for k in ["id", "display_name", "role", "joined_at"]} for p in store.people(project_id)]


@app.patch("/api/projects/{project_id}/people/{person_id}")
def patch_person(project_id: str, person_id: str, payload: PersonPatch, request: Request):
    actor = require(project_id, request, {"owner"})
    return store.update_person(project_id, person_id, payload.model_dump(exclude_unset=True), actor["id"])


@app.delete("/api/projects/{project_id}/people/{person_id}")
def delete_person(project_id: str, person_id: str, request: Request):
    actor = require(project_id, request, {"owner"})
    if actor["id"] == person_id:
        raise HTTPException(400, "Use another Owner to remove your own membership")
    store.remove_person(project_id, person_id, actor["id"])
    return {"ok": True}


@app.post("/api/projects/{project_id}/people/{person_id}/regenerate-link")
def recovery_link(project_id: str, person_id: str, request: Request):
    actor = require(project_id, request, {"owner"})
    token = store.regenerate_access(project_id, person_id, actor["id"])
    return {"recovery_url": f"{settings.base_url}/recover/{project_id}?token={token}", "one_time": True}


# Cards
def _card_visible_to(card: dict[str, Any], actor: dict[str, Any]) -> bool:
    return (card.get("visibility") or "everyone") == "everyone" or card.get("created_by") == actor.get("id")

def _visible_card(project_id: str, card_id: str, actor: dict[str, Any]) -> dict[str, Any]:
    card = store.get_card(project_id, card_id)
    if not _card_visible_to(card, actor):
        # Do not reveal that a private card exists to another project member.
        raise HTTPException(404, "Card not found")
    return card

@app.get("/api/projects/{project_id}/cards")
def cards(project_id: str, request: Request, type: str | None = None, status: str | None = None, tag: str | None = None, assignee: str | None = None):
    actor = require(project_id, request)
    items = [x for x in store.cards(project_id) if _card_visible_to(x, actor)]
    if type: items = [x for x in items if x.get("type") == type]
    if status: items = [x for x in items if x.get("status") == status]
    if tag: items = [x for x in items if tag in x.get("tags", [])]
    if assignee: items = [x for x in items if assignee in x.get("assignees", [])]
    return items


@app.post("/api/projects/{project_id}/cards")
def add_card(project_id: str, payload: CardCreate, request: Request, response: Response):
    actor = require(project_id, request, {"owner", "member"})
    key = request.headers.get("X-Idempotency-Key")
    card, replayed = store.create_card(project_id, payload.model_dump(), actor["id"], key)
    if replayed:
        response.headers["X-Idempotency-Replayed"] = "true"
    return card


@app.get("/api/projects/{project_id}/cards/{card_id}")
def card(project_id: str, card_id: str, request: Request):
    actor = require(project_id, request)
    return _visible_card(project_id, card_id, actor)


@app.patch("/api/projects/{project_id}/cards/{card_id}")
def patch_card(project_id: str, card_id: str, payload: CardPatch, request: Request):
    actor = require(project_id, request, {"owner", "member"})
    card = _visible_card(project_id, card_id, actor)
    patch = payload.model_dump(exclude_unset=True)
    if (card.get("edit_access") or "public") == "private" and card.get("created_by") != actor["id"]:
        raise HTTPException(403, "Only the card creator can edit a Private card")
    if "edit_access" in patch and card.get("created_by") != actor["id"]:
        raise HTTPException(403, "Only the card creator can change card edit access")
    if "visibility" in patch and card.get("created_by") != actor["id"]:
        raise HTTPException(403, "Only the card creator can change card visibility")
    return store.update_card(project_id, card_id, patch, actor["id"])


@app.get("/api/projects/{project_id}/cards/{card_id}/activity")
def card_activity(project_id: str, card_id: str, request: Request):
    actor = require(project_id, request)
    _visible_card(project_id, card_id, actor)
    return store.card_activity(project_id, card_id, 100)


@app.delete("/api/projects/{project_id}/cards/{card_id}")
def delete_card(project_id: str, card_id: str, request: Request):
    actor = require(project_id, request, {"owner", "member"})
    card = _visible_card(project_id, card_id, actor)
    if card.get("created_by") != actor["id"]:
        raise HTTPException(403, "Only the card creator can delete this card")
    store.delete_card(project_id, card_id, actor["id"]); return {"ok": True}


@app.get("/api/projects/{project_id}/cards/{card_id}/ics")
def card_ics(project_id: str, card_id: str, request: Request):
    actor = require(project_id, request)
    c = _visible_card(project_id, card_id, actor)
    if not c.get("start"):
        raise HTTPException(400, "This card has no start date")
    uid = f"{card_id}@popup-workspace"
    def ics_escape(v: str) -> str: return (v or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")
    def dt(v: str | None) -> str:
        if not v: return ""
        return v.replace("-", "").replace(":", "").replace("+00:00", "Z").replace("Z", "Z")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Cocklebur//EN", "BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}", f"DTSTART:{dt(c['start'])}"]
    if c.get("end"): lines.append(f"DTEND:{dt(c['end'])}")
    lines += [f"SUMMARY:{ics_escape(c['title'])}", f"DESCRIPTION:{ics_escape(c.get('content') or c.get('description') or '')}", "END:VEVENT", "END:VCALENDAR", ""]
    return Response("\r\n".join(lines), media_type="text/calendar", headers={"Content-Disposition": f'attachment; filename="{card_id}.ics"'})


@app.get("/api/projects/{project_id}/tags")
def tags(project_id: str, request: Request):
    actor = require(project_id, request)
    tags = sorted({t for c in store.cards(project_id) if _card_visible_to(c, actor) for t in c.get("tags", [])})
    return tags


# Announcements
@app.get("/api/projects/{project_id}/announcements")
def announcements(project_id: str, request: Request):
    require(project_id, request); return store.announcements(project_id)


@app.post("/api/projects/{project_id}/announcements")
def add_announcement(project_id: str, payload: MessageCreate, request: Request):
    actor = require(project_id, request, {"owner", "member"}); return store.add_announcement(project_id, payload.model_dump(), actor["id"])


@app.patch("/api/projects/{project_id}/announcements/{msg_id}")
def edit_announcement(project_id: str, msg_id: str, payload: AnnouncementEdit, request: Request):
    actor = require(project_id, request, {"owner", "member"})
    target = next((m for m in store.announcements(project_id) if m.get("id") == msg_id), None)
    if not target: raise HTTPException(404, "Announcement not found")
    if actor["role"] != "owner" and target.get("actor_id") != actor["id"]: raise HTTPException(403, "Only the author or an Owner can edit this announcement")
    store.mutate_announcement(project_id, msg_id, "edit", actor["id"], body=payload.body, title=payload.title or "", tags=payload.tags); return {"ok": True}


@app.delete("/api/projects/{project_id}/announcements/{msg_id}")
def delete_announcement(project_id: str, msg_id: str, request: Request):
    actor = require(project_id, request, {"owner", "member"})
    target = next((m for m in store.announcements(project_id) if m.get("id") == msg_id), None)
    if not target: raise HTTPException(404, "Announcement not found")
    if actor["role"] != "owner" and target.get("actor_id") != actor["id"]: raise HTTPException(403, "Only the author or an Owner can delete this announcement")
    store.mutate_announcement(project_id, msg_id, "delete", actor["id"]); return {"ok": True}


@app.post("/api/projects/{project_id}/announcements/{msg_id}/pin")
def pin_announcement(project_id: str, msg_id: str, request: Request, pinned: bool = Body(embed=True)):
    actor = require(project_id, request, {"owner"}); store.mutate_announcement(project_id, msg_id, "pin", actor["id"], pinned=pinned); return {"ok": True}


# Discussions
@app.get("/api/projects/{project_id}/channels")
def channels(project_id: str, request: Request):
    p = require(project_id, request); return [c for c in store.channels(project_id) if store.can_view_channel(c, p)]


@app.post("/api/projects/{project_id}/channels")
def add_channel(project_id: str, payload: ChannelCreate, request: Request):
    actor = require(project_id, request, {"owner"}); return store.create_channel(project_id, payload.model_dump(), actor["id"])


@app.patch("/api/projects/{project_id}/channels/{channel_id}")
def patch_channel(project_id: str, channel_id: str, request: Request, payload: dict[str, Any] = Body(...)):
    actor = require(project_id, request, {"owner"}); return store.update_channel(project_id, channel_id, payload, actor["id"])


@app.delete("/api/projects/{project_id}/channels/{channel_id}")
def remove_channel(project_id: str, channel_id: str, request: Request):
    actor = require(project_id, request, {"owner"}); store.delete_channel(project_id, channel_id, actor["id"]); return {"ok": True}


@app.get("/api/projects/{project_id}/channels/{channel_id}/threads")
def threads(project_id: str, channel_id: str, request: Request):
    p = require(project_id, request); get_channel_for_person(project_id, channel_id, p); return store.threads(project_id, channel_id)


@app.post("/api/projects/{project_id}/channels/{channel_id}/threads")
def add_thread(project_id: str, channel_id: str, payload: MessageCreate, request: Request):
    actor = require(project_id, request, {"owner", "member"}); get_channel_for_person(project_id, channel_id, actor); return store.create_thread(project_id, channel_id, payload.model_dump(), actor["id"])


@app.get("/api/projects/{project_id}/channels/{channel_id}/threads/{thread_id}")
def thread(project_id: str, channel_id: str, thread_id: str, request: Request):
    p = require(project_id, request); get_channel_for_person(project_id, channel_id, p); return store.thread_messages(project_id, channel_id, thread_id)


@app.post("/api/projects/{project_id}/channels/{channel_id}/threads/{thread_id}/replies")
def add_reply(project_id: str, channel_id: str, thread_id: str, payload: ReplyCreate, request: Request):
    actor = require(project_id, request, {"owner", "member"}); get_channel_for_person(project_id, channel_id, actor); return store.reply(project_id, channel_id, thread_id, payload.body, actor["id"])


@app.patch("/api/projects/{project_id}/channels/{channel_id}/threads/{thread_id}/messages/{msg_id}")
def edit_message(project_id: str, channel_id: str, thread_id: str, msg_id: str, payload: MessageEdit, request: Request):
    actor = require(project_id, request, {"owner", "member"}); get_channel_for_person(project_id, channel_id, actor)
    target = next((m for m in store.thread_messages(project_id, channel_id, thread_id) if m.get("id") == msg_id), None)
    if not target: raise HTTPException(404, "Message not found")
    if actor["role"] != "owner" and target.get("actor_id") != actor["id"]: raise HTTPException(403, "Only the author or an Owner can edit this message")
    store.mutate_message(project_id, channel_id, thread_id, msg_id, "edit", actor["id"], body=payload.body); return {"ok": True}


@app.delete("/api/projects/{project_id}/channels/{channel_id}/threads/{thread_id}/messages/{msg_id}")
def delete_message(project_id: str, channel_id: str, thread_id: str, msg_id: str, request: Request):
    actor = require(project_id, request, {"owner", "member"}); get_channel_for_person(project_id, channel_id, actor)
    target = next((m for m in store.thread_messages(project_id, channel_id, thread_id) if m.get("id") == msg_id), None)
    if not target: raise HTTPException(404, "Message not found")
    if actor["role"] != "owner" and target.get("actor_id") != actor["id"]: raise HTTPException(403, "Only the author or an Owner can delete this message")
    store.mutate_message(project_id, channel_id, thread_id, msg_id, "delete", actor["id"]); return {"ok": True}


# Files
@app.get("/api/projects/{project_id}/files")
def files(project_id: str, request: Request, query: str = ""):
    p = require(project_id, request)
    if query: return store.search(project_id, query, p)["files"]
    return store.files(project_id)


@app.get("/api/projects/{project_id}/upload-limits")
def upload_limits(project_id: str, request: Request):
    require(project_id, request, {"owner", "member"})
    project_settings = store.get_settings(project_id)
    quota_bytes = int(project_settings.get("quota_mb", settings.default_project_quota_mb)) * 1024 * 1024
    used_bytes = store.project_size_bytes(project_id)
    max_upload_bytes = settings.max_upload_mb * 1024 * 1024
    return {
        "max_upload_mb": settings.max_upload_mb,
        "max_upload_bytes": max_upload_bytes,
        "quota_mb": int(project_settings.get("quota_mb", settings.default_project_quota_mb)),
        "quota_bytes": quota_bytes,
        "used_bytes": used_bytes,
        "remaining_bytes": max(0, quota_bytes - used_bytes),
    }


@app.post("/api/projects/{project_id}/files")
async def upload_file(
    project_id: str,
    request: Request,
    file: UploadFile = File(...),
    description: str = Form(""),
    linked_card_ids: list[str] = Form(default=[]),
    linked_card_id: str | None = Form(None),
):
    actor = require(project_id, request, {"owner", "member"})
    data = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
    if len(data) > settings.max_upload_mb * 1024 * 1024: raise HTTPException(413, f"File exceeds the {settings.max_upload_mb} MB per-file upload limit")
    links = list(dict.fromkeys([*(linked_card_ids or []), *([linked_card_id] if linked_card_id else [])]))
    return store.add_file(project_id, file.filename or "file", data, description, links, actor["id"])


@app.get("/api/projects/{project_id}/files/{file_id}")
def file_meta(project_id: str, file_id: str, request: Request):
    require(project_id, request); return store.file_meta(project_id, file_id)


@app.get("/api/projects/{project_id}/files/{file_id}/download")
def download_file(project_id: str, file_id: str, request: Request):
    require(project_id, request); meta = store.file_meta(project_id, file_id)
    path = store._path(project_id, f"files/{meta['stored_name']}")
    return FileResponse(path, filename=meta["name"], media_type="application/octet-stream")


@app.patch("/api/projects/{project_id}/files/{file_id}")
def patch_file(project_id: str, file_id: str, request: Request, payload: dict[str, Any] = Body(...)):
    actor = require(project_id, request, {"owner", "member"}); return store.update_file_meta(project_id, file_id, payload, actor["id"])


@app.delete("/api/projects/{project_id}/files/{file_id}")
def remove_file(project_id: str, file_id: str, request: Request):
    actor = require(project_id, request, {"owner", "member"}); store.delete_file(project_id, file_id, actor["id"]); return {"ok": True}


# Search/activity/unread
@app.get("/api/projects/{project_id}/search")
def search(project_id: str, request: Request, q: str):
    p = require(project_id, request); return store.search(project_id, q, p)


@app.get("/api/projects/{project_id}/activity")
def activity(project_id: str, request: Request):
    actor = require(project_id, request); return store.activity_for_person(project_id, actor, 200)


@app.get("/api/projects/{project_id}/unread-counts")
def unread(project_id: str, request: Request):
    p = require(project_id, request); return store.unread_counts(project_id, p)


@app.post("/api/projects/{project_id}/mark-seen")
def mark_seen(project_id: str, payload: SeenUpdate, request: Request):
    p = require(project_id, request); store.mark_seen(project_id, p["id"], payload.module, payload.cursor); return {"ok": True}


# Settings/lifecycle/export
@app.get("/api/projects/{project_id}/settings")
def project_settings(project_id: str, request: Request):
    require(project_id, request, {"owner"}); s = store.get_settings(project_id); return {k: v for k, v in s.items() if k not in {"invite_hash", "pin_hash"}}


@app.patch("/api/projects/{project_id}/settings")
def patch_settings(project_id: str, payload: SettingsPatch, request: Request):
    p = require(project_id, request, {"owner"}); return store.update_settings(project_id, payload.model_dump(exclude_unset=True), p["id"])


@app.post("/api/projects/{project_id}/close")
def close_project(project_id: str, request: Request):
    p = require(project_id, request, {"owner"}); return store.set_status(project_id, "closing", p["id"])


@app.get("/api/projects/{project_id}/close/summary")
def close_summary(project_id: str, request: Request):
    require(project_id, request, {"owner"}); return {**store.close_summary(project_id), "export_current": store.can_delete_after_export(project_id)}


@app.post("/api/projects/{project_id}/archive")
def archive_project(project_id: str, request: Request):
    p = require(project_id, request, {"owner"}); return store.set_status(project_id, "archived", p["id"])


@app.get("/api/projects/{project_id}/export")
def export_project(project_id: str, request: Request):
    require(project_id, request, {"owner", "member"})
    path, _meta = store.export_project(project_id)
    return FileResponse(path, filename=path.name, media_type="application/zip", background=BackgroundTask(path.unlink, missing_ok=True))


@app.delete("/api/projects/{project_id}")
def delete_project(project_id: str, request: Request, confirm: bool = False):
    require(project_id, request, {"owner"})
    if not confirm: raise HTTPException(400, "confirm=true is required")
    store.delete_project(project_id, require_export=True); return {"ok": True}


@app.post("/api/render-markdown")
def markdown_preview(payload: dict[str, str] = Body(...)):
    return {"html": render_markdown(payload.get("text", ""))}
