# Multi-device access — Server 0.2.18.1

Cocklebur Server does not require a global username/password account to use the same identity on several devices.

## Project identities

For an existing Owner, Member or Viewer:

```text
Your profile
→ Manage devices
→ Add another device
→ scan QR or open one-time link on the other browser
→ confirm device name
```

The new browser receives its own session credential but retains the exact same `person_id`, display name and role.

An Invite is different: accepting an Invite creates a new project person. Do not use an Invite merely to add your own phone or second browser.

## Host

For Instance Host:

```text
Host access
→ Manage Host devices
→ Add another device
```

Adding a Host device is normal multi-device access and does not consume or rotate the Host recovery code.

## Recovery

Recovery remains a break-glass path:

- Host recovery code: restore Instance Host after browser access is lost.
- Owner recovery code: restore an Owner identity after project browser access is lost.
- Owner-generated member recovery link: restore a collaborator when they no longer have normal access.

Use **Add another device** for planned multi-device use and **Recovery** for lost access.

## Security properties

- Device links are random high-entropy bearer secrets stored server-side only as hashes.
- Links expire after 10 minutes.
- Links are single-use.
- Generating a new link replaces the previous outstanding link for that identity.
- Existing devices remain active when a new device is linked.
- Each non-current device session can be revoked independently.
- Current-device self-revocation is blocked to avoid accidental lockout.
