# Security Notes

## Trust boundaries

Cocklebur separates three layers:

1. **Infrastructure Admin / Deployer** — controls the host machine, Docker, storage, backups and network.
2. **Instance Host / delegated instance permissions** — controls Cocklebur-level Create / Import authorization.
3. **Project roles** — Owner / Member / Viewer inside individual projects.

Infrastructure administrators are not automatically assigned a Cocklebur app role. However, server/root/storage administrators are technically capable of reading, altering, restoring or deleting self-hosted data. Application permissions cannot override control of the underlying infrastructure.

## Host bootstrap

The configured bootstrap key is accepted only while the Cocklebur instance is unclaimed. Claiming Host creates persistent Host auth state under `/data` and issues a Host recovery code. After claim, bootstrap-key login is rejected.

Host recovery preserves existing valid Host sessions and rotates the recovery code.

## Delegated instance permissions

Create and Import can be granted independently to an existing project identity. The server validates those permissions against that identity's project-scoped HttpOnly browser credential. Removing the project identity removes its associated instance grant.

Instance permissions are installation-specific and are **not exported inside project packs**.

## Deployment

- Use HTTPS for Internet-facing deployments.
- Do not expose the raw Docker port publicly.
- Run exactly one application worker.
- Keep `/data` persistent and backed up.
- Protect bootstrap keys, Host/Owner recovery codes, invite/recovery links and project cookies.

## Reporting a security issue

Do not publish live credentials, private project data or exploit details in a public issue.
