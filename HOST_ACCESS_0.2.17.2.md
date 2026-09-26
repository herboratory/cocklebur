# Host access — Server 0.2.17.2

Cocklebur Server uses one deployment key name and two Cocklebur-managed credentials.

```text
COCKLEBUR_BOOTSTRAP_KEY
        ↓ claim an unclaimed Host
Host session cookie
        ↓ normal browser access
Host recovery code
        ↓ restore access after cookie loss; code rotates
```

## Deployment

Server mode requires:

```dotenv
POPUP_APP_MODE=server
COCKLEBUR_BOOTSTRAP_KEY=<long-random-secret>
```

## First claim

Open Cocklebur, choose **Claim Host**, and enter the Bootstrap Key. Cocklebur creates a Host browser session and shows a Host recovery code. Store that recovery code safely.

After Host has been claimed, the Bootstrap Key is not a normal Host login password.

## New browser / cleared cookies

Choose **Host recovery** and enter the current Host recovery code. Successful recovery creates a new Host browser session and rotates the recovery code. Store the newly displayed code; the previous recovery code is no longer valid.

## Break-glass reset

If all Host browser sessions and the current recovery code are unavailable, an infrastructure administrator can run:

```bash
python -m app.admin host-status
python -m app.admin reset-host --yes
```

The reset backs up `.instance_auth.json`, clears only Host credentials, and preserves projects and delegated instance grants. Then claim Host again with `COCKLEBUR_BOOTSTRAP_KEY`.
