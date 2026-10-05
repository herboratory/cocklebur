from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=5000)
    mode: Literal["local", "server"] = "local"
    expiry: str | None = None
    timezone: str = "UTC"
    owner_name: str = Field(default="Owner", min_length=1, max_length=100)
    storage_path: str | None = None


class ProjectPatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=5000)
    expiry: str | None = None
    timezone: str | None = None
    expected_version: int


class CardCreate(BaseModel):
    type: Literal["task", "event", "note"] = "task"
    title: str = Field(min_length=1, max_length=240)
    status: str = "todo"
    start: str | None = None
    end: str | None = None
    all_day: bool = False
    assignees: list[str] = []
    description: str = ""
    content: str = ""
    tags: list[str] = []
    linked_files: list[str] = []
    edit_access: Literal["public", "private"] = "public"
    visibility: Literal["everyone", "private"] = "everyone"


class CardPatch(BaseModel):
    expected_version: int
    type: Literal["task", "event", "note"] | None = None
    title: str | None = Field(default=None, min_length=1, max_length=240)
    status: str | None = None
    start: str | None = None
    end: str | None = None
    all_day: bool | None = None
    assignees: list[str] | None = None
    description: str | None = None
    content: str | None = None
    tags: list[str] | None = None
    linked_files: list[str] | None = None
    edit_access: Literal["public", "private"] | None = None
    visibility: Literal["everyone", "private"] | None = None


class MessageCreate(BaseModel):
    title: str | None = Field(default=None, max_length=240)
    body: str = Field(min_length=1, max_length=50_000)
    tags: list[str] = []


class MessageEdit(BaseModel):
    body: str = Field(min_length=1, max_length=50_000)


class AnnouncementEdit(BaseModel):
    title: str | None = Field(default=None, max_length=240)
    body: str = Field(min_length=1, max_length=50_000)
    tags: list[str] = []


class ReplyCreate(BaseModel):
    body: str = Field(min_length=1, max_length=50_000)


class ChannelCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    visibility: Literal["everyone", "roles", "members"] = "everyone"
    roles: list[Literal["owner", "member", "viewer"]] = []
    members: list[str] = []


class JoinRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)
    token: str = Field(min_length=10)
    pin: str | None = None


class PersonPatch(BaseModel):
    role: Literal["owner", "member", "viewer"] | None = None
    display_name: str | None = Field(default=None, min_length=1, max_length=100)


class SettingsPatch(BaseModel):
    expected_version: int
    expiry: str | None = None
    quota_mb: int | None = Field(default=None, ge=10, le=1_000_000)
    pin: str | None = Field(default=None, max_length=20)


class SeenUpdate(BaseModel):
    module: Literal["announcements", "discussion", "cards", "files", "activity"]
    cursor: str


class SelfPatch(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)


class HostClaim(BaseModel):
    key: str = Field(min_length=1, max_length=500)
    display_name: str = Field(default="Host", min_length=1, max_length=100)


class HostRecover(BaseModel):
    code: str = Field(min_length=8, max_length=200)


class InstancePermissionPatch(BaseModel):
    can_create_projects: bool = False
    can_import_projects: bool = False


class OwnerRecover(BaseModel):
    code: str = Field(min_length=8, max_length=200)


class WorkspaceImportCommit(BaseModel):
    batch_id: str = Field(min_length=8, max_length=120)
    duplicate_policy: Literal["skip", "new_id"] = "skip"


class UpdateStageCommit(BaseModel):
    stage_id: str = Field(min_length=8, max_length=120)
