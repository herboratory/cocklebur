# Host access — Server 0.2.18.1

Cocklebur Server uses three distinct Host-access concepts:

```text
COCKLEBUR_BOOTSTRAP_KEY
        ↓ claim an unclaimed Host
Host browser sessions
        ↓ normal access on one or more devices
Host recovery code
        ↓ restore access after normal sessions are lost
```

## First claim

Configure `COCKLEBUR_BOOTSTRAP_KEY`, open Cocklebur and choose **Claim Host**. Cocklebur creates the first Host browser session and shows a Host recovery code. Save the recovery code.

## Add another Host device

For planned computer + phone / multiple-browser access:

```text
Host access → Manage Host devices → Add another device
```

Open the one-time link or scan the QR code on the other device. The new device becomes another Host browser session. Existing Host devices remain signed in, and the Host recovery code is not rotated.

## Recovery

Use **Host recovery** only when normal Host browser access is unavailable. Recovery creates another Host browser session and rotates the recovery code.

## Break-glass

If every Host session and the current recovery code are unavailable:

```bash
python -m app.admin host-status
python -m app.admin reset-host --yes
```

The reset preserves projects and delegated instance grants, then returns the instance to Claim Host state.
