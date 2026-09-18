# Updating Cocklebur Server

Project data and instance auth state live under the persistent data directory (`/data` in the supplied Docker configuration).

## Before updating

1. Export important active projects.
2. Back up the persistent Cocklebur volume.
3. Record the current app version.

## Docker

```bash
docker compose down
docker compose build --pull
docker compose up -d
```

Do **not** use `docker compose down -v` for a normal update.

## Updating from 0.2.15 to 0.2.16

0.2.16 introduces persistent instance-level Host auth.

Existing project data remains compatible and project pack format stays `1.0`. On the first 0.2.16 start, an older server has no `.instance_auth.json` yet, so the instance appears **unclaimed**. Use the existing `COCKLEBUR_HOST_KEY` (or the new `COCKLEBUR_BOOTSTRAP_KEY`) once to **Claim Host**, then save the generated Host recovery code.

After claim, the bootstrap key is no longer accepted for Host login.
