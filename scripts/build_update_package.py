from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import tempfile
import zipfile
from pathlib import Path

FORMAT = "cocklebur-server-update"
FORMAT_VERSION = "1.0"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser(description="Build a Cocklebur Server Update staging package")
    ap.add_argument("--source", required=True, help="Directory containing files to place under payload/")
    ap.add_argument("--target-version", required=True)
    ap.add_argument("--minimum-source-version", required=True)
    ap.add_argument("--update-id", default=None)
    ap.add_argument("--output", required=True)
    args = ap.parse_args()

    source = Path(args.source).expanduser().resolve()
    if not source.is_dir():
        raise SystemExit(f"Source directory not found: {source}")
    output = Path(args.output).expanduser().resolve()
    output.parent.mkdir(parents=True, exist_ok=True)

    forbidden_roots = {"data", ".git", ".github"}
    forbidden_names = {".env", ".instance_secret", ".instance_id", ".host_key", ".instance_auth.json"}

    with tempfile.TemporaryDirectory(prefix="cocklebur_update_build_") as td:
        root = Path(td) / "package"
        payload = root / "payload"
        payload.mkdir(parents=True)
        checksums: dict[str, str] = {}
        for src in sorted(source.rglob("*")):
            if not src.is_file():
                continue
            rel_src = src.relative_to(source)
            if not rel_src.parts or rel_src.parts[0] in forbidden_roots or src.name in forbidden_names:
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
            "update_id": args.update_id or f"SERVER-{args.target_version}",
            "minimum_source_version": args.minimum_source_version,
            "target_version": args.target_version,
            "restart_required": True,
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
