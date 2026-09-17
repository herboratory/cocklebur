# Security

## Reporting a security issue

Please do not post secrets, host keys, invite/recovery tokens, private project data, or other sensitive material in a public GitHub issue.

For ordinary bugs, use the GitHub issue tracker and remove sensitive information before posting.

## Deployment notes

Cocklebur Server is intended to run behind HTTPS through a reverse proxy or tunnel.

- Do not expose the plain application HTTP port directly to the public internet.
- Use a long random `COCKLEBUR_HOST_KEY`.
- Keep `.env` private.
- Back up important project data and exported project packs.
- Keep the Server package updated when new releases are published.

Cocklebur is self-hosted software. The administrator of the host machine can access the underlying project files.

Application-level "Only me" visibility is not filesystem encryption.
