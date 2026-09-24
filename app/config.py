from __future__ import annotations

import os
import secrets
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    app_mode: str
    base_url: str
    secret_key: str
    max_upload_mb: int
    max_import_mb: int
    default_project_quota_mb: int
    max_update_mb: int
    instance_id: str
    host_key: str | None


def load_settings() -> Settings:
    data_dir = Path(os.getenv("POPUP_DATA_DIR", "./data")).expanduser().resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    app_mode = os.getenv("POPUP_APP_MODE", "local").strip().lower()
    if app_mode not in {"local", "server"}:
        app_mode = "local"
    secret_file = data_dir / ".instance_secret"
    if os.getenv("POPUP_SECRET_KEY"):
        secret_key = os.environ["POPUP_SECRET_KEY"]
    elif secret_file.exists():
        secret_key = secret_file.read_text("utf-8").strip()
    else:
        secret_key = secrets.token_urlsafe(48)
        secret_file.write_text(secret_key, "utf-8")
        try:
            os.chmod(secret_file, 0o600)
        except OSError:
            pass
    instance_file = data_dir / ".instance_id"
    if instance_file.exists():
        instance_id = instance_file.read_text("utf-8").strip()
    else:
        instance_id = secrets.token_hex(16)
        instance_file.write_text(instance_id, "utf-8")
    host_key: str | None = None
    if app_mode == "server":
        host_file = data_dir / ".host_key"
        env_host_key = os.getenv("COCKLEBUR_HOST_KEY", "").strip()
        if env_host_key:
            host_key = env_host_key
        elif host_file.exists():
            host_key = host_file.read_text("utf-8").strip()
        else:
            host_key = secrets.token_urlsafe(24)
            host_file.write_text(host_key, "utf-8")
            try:
                os.chmod(host_file, 0o600)
            except OSError:
                pass

    return Settings(
        data_dir=data_dir,
        app_mode=app_mode,
        base_url=os.getenv("POPUP_BASE_URL", "http://127.0.0.1:8000").rstrip("/"),
        secret_key=secret_key,
        max_upload_mb=int(os.getenv("POPUP_MAX_UPLOAD_MB", "50")),
        max_import_mb=int(os.getenv("POPUP_IMPORT_MAX_MB", "2048")),
        default_project_quota_mb=int(os.getenv("POPUP_PROJECT_QUOTA_MB", "1024")),
        max_update_mb=int(os.getenv("COCKLEBUR_UPDATE_MAX_MB", "512")),
        instance_id=instance_id,
        host_key=host_key,
    )
