# Managed updates — Server 0.2.18.1

The standard Server image now runs a small supervisor as PID 1. Uvicorn runs as its unprivileged child process.

The supervisor has no Docker socket and no Kubernetes API credential. It only manages Cocklebur application release directories inside the persistent `/data/.runtime` area.

## Flow

```text
Host uploads update
→ web app validates + backs up + stages
→ Host clicks Apply update
→ web app writes local apply request
→ supervisor independently verifies checksums/manifest
→ new runtime release copied to /data/.runtime/releases
→ active release switched atomically
→ Uvicorn restarted
→ /health must report target version
→ success, or automatic code rollback
```

Host/project credentials and project data remain in `/data` outside the active runtime release.

## Important

0.2.17.2 and older do not contain this supervisor, so moving onto the managed updater requires one final normal deployment. Once a managed-updater image is installed, compatible runtime-only updates can be applied from Update center.
