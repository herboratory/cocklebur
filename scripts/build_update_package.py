from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

FORMAT = "cocklebur-server-update"
FORMAT_VERSION = "1.1"
APPLY_MODE = "managed-runtime-v1"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a Cocklebur managed-runtime update package")
    ap.add_argument("--source", required=True, help="Runtime source directory; must contain app/ and requirements.txt")
    ap.add_argument("--target-version", required=True)
    ap.add_argument("--minimum-source-version", required=True)
    ap.add_argument("--update-id", default=None)
    ap.add_argument("--output", required=True)
    ap.add_argument("--health-timeout-seconds", type=int, default=45)
    args = ap.parse_args()

    source = Path(args.source).expanduser().resolve()
    if not source.is_dir():
        raise SystemExit(f"Source directory not found: {source}")
    if not (source / "app" / "__init__.py").is_file() or not (source / "requirements.txt").is_file():
        raise SystemExit("Managed runtime source must contain app/__init__.py and requirements.txt")
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    forbidden_roots = {"data", ".git", ".github", "bootstrap"}
    forbidden_names = {".env", ".instance_secret", ".instance_id", ".host_key", ".instance_auth.json"}
    allowed_top_level = {"app", "requirements.txt"}

    with tempfile.TemporaryDirectory(prefix="cocklebur_update_build_") as td:
        root = Path(td) / "package"
        payload = root / "payload"
        payload.mkdir(parents=True)
        checksums: dict[str, str] = {}
        for src in sorted(source.rglob("*")):
            if not src.is_file():
                continue
            rel_src = src.relative_to(source)
            if not rel_src.parts or rel_src.parts[0] not in allowed_top_level:
                continue
            if rel_src.parts[0] in forbidden_roots or src.name in forbidden_names:
                raise SystemExit(f"Forbidden update source path: {rel_src.as_posix()}")
            dest = payload / rel_src
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            rel = dest.relative_to(root).as_posix()
            checksums[rel] = sha256(dest)

        if not checksums:
            raise SystemExit("No payload files found")
        manifest = {
            "format": FORMAT,
            "format_version": FORMAT_VERSION,
            "apply_mode": APPLY_MODE,
            "update_id": args.update_id or f"SERVER-{args.target_version}",
            "minimum_source_version": args.minimum_source_version,
            "target_version": args.target_version,
            "restart_required": True,
            "health_timeout_seconds": max(3, int(args.health_timeout_seconds)),
            "data_migration": False,
        }
        (root / "update-manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", "utf-8")
        (root / "checksums.json").write_text(json.dumps(checksums, ensure_ascii=False, indent=2) + "\n", "utf-8")
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(root).as_posix())

    print(f"Built {output}")
    print(f"SHA-256 {sha256(output)}")


if __name__ == "__main__":
    main()
