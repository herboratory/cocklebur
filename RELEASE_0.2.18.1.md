# Cocklebur Server 0.2.18.1

## Multi-device Access & Managed Updates

Cocklebur Server 0.2.18.1 adds first-class multi-device access and completes the foundation for managed Server updates.

Users can now use the same Cocklebur identity across multiple browsers and devices without creating duplicate project members. Server installations also gain a managed runtime capable of applying compatible application updates with restart, health verification, and rollback.

---

## Multi-device access

Cocklebur now treats multiple browsers and devices as multiple sessions belonging to the same identity.

Project Owners, Members, and Viewers can:

- view their active device sessions;
- add another device;
- generate a short-lived, single-use device link;
- open the link directly or scan its QR code on another device;
- use the same `person_id` and project role across devices;
- revoke individual device sessions.

Adding another device does not create another project member.

For example:

```text
Inger · Owner · person_id u_123

MacBook Safari  → Device session A
iPhone Safari   → Device session B
Chrome          → Device session C
```

All sessions continue to represent the same Cocklebur identity.

---

## Clear access model

Cocklebur now distinguishes three separate operations:

```text
Invite
= add a new person to a project

Add device
= give an existing person access on another device

Recovery
= restore access after normal access has been lost
```

Recovery credentials are therefore no longer the normal mechanism for using Cocklebur on another device.

---

## Host multi-device access

Instance Host access also supports multiple devices.

A Host can:

- view active Host device sessions;
- add another Host device;
- link another browser using a one-time device link;
- revoke individual Host sessions.

Adding another Host device does not rotate the Host recovery code.

The Host credential lifecycle remains:

```text
COCKLEBUR_BOOTSTRAP_KEY
→ first Host claim

Host session
→ normal day-to-day access

Host recovery code
→ emergency access recovery
```

`COCKLEBUR_HOST_KEY` is no longer used.

---

## Device management

Project members can access device management directly from their own entry in the Members view.

Existing Cocklebur browser credentials remain compatible and are represented as legacy sessions when necessary.

The previous hidden fixed session limit has been removed in favour of explicit device/session management.

---

## Managed Server updates

The Update Center can now progress beyond package staging.

For compatible runtime updates, the workflow is:

```text
Upload
→ Validate
→ Backup
→ Stage
→ Apply
→ Restart
→ Health check
```

If the new runtime fails its health check:

```text
Failed update
→ restore previous runtime
→ restart
→ rollback
```

Cocklebur project data remains outside the application runtime and is not replaced by an application update.

---

## Managed runtime architecture

The Cocklebur web process does not receive unrestricted Docker or Kubernetes administration privileges.

A narrow runtime supervisor handles:

- switching staged application releases;
- restarting the Cocklebur application;
- health verification;
- automatic runtime rollback.

Application-level Host privileges remain separate from infrastructure-level control.

---

## Update compatibility

Managed Runtime v1 is intended for application updates that do not require changes to the underlying Python dependency environment.

Updates that change container-level dependencies or infrastructure requirements still require a normal Server deployment.

This keeps in-app updating narrower and safer than giving Cocklebur arbitrary container or host administration privileges.

---

## Existing Server features retained

0.2.18.1 also retains:

- Workspace Bundle export/import;
- Note Cards;
- idempotent Card creation;
- safer `Saving…` behaviour;
- delegated instance Create / Import permissions;
- Host bootstrap and recovery;
- break-glass Host reset tooling;
- pre-update data backups;
- Update Center package validation;
- Owner / Member / Viewer project roles.

---

## Data and compatibility

- Project Pack format remains **1.0**.
- Existing project identities remain compatible.
- Existing Host state and recovery information remain compatible.
- Project data remains separate from application runtime releases.
- Device credentials are not carried inside portable Project Packs.
- Existing project roles and permissions are unchanged.

---

## Deployment note

This release introduces the managed-runtime supervisor required for future in-app updates.

Existing installations upgrading from an earlier Cocklebur Server version must deploy **0.2.18.1 normally once**.

After 0.2.18.1 is installed, future compatible runtime releases can be delivered through the Cocklebur Update Center without requiring a manual Server redeployment each time.

Server deployments require:

```env
POPUP_APP_MODE=server
COCKLEBUR_BOOTSTRAP_KEY=<your-secret>
```

After deployment, verify:

```bash
curl https://your-cocklebur-server/health
```

The reported version should be:

```text
0.2.18.1
```

For an existing deployment, the persistent `/data` volume must be preserved during upgrade.
