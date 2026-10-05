# Cocklebur Server 0.2.18.1

**Release marker:** SERVER-0.2.18.1-MANAGED-UPDATES

Cocklebur Server 0.2.18.1 turns multi-device access into a normal Server workflow instead of using recovery as a workaround.

## Multi-device access

A single Cocklebur identity can now be used concurrently in multiple browsers/devices while keeping the same `person_id` and project role.

```text
Person: Inger · Owner · u_xxx
├── Safari on Mac
├── Safari on iPhone
└── Chrome on iPad
```

Project Owner, Member and Viewer identities can open **Your profile → Manage devices → Add another device** to generate a short-lived, one-time device link and QR code. Opening that link on another browser adds a new session to the same identity; it does not create another member.

Device links:

- expire after 10 minutes;
- are single-use;
- preserve the existing role and person ID;
- do not invalidate existing devices;
- can be revoked individually from the device list.

The current device cannot revoke itself through the device-management UI/API.

## Host multi-device access

Instance Host now has the same normal device-linking flow:

```text
Host access → Manage Host devices → Add another device
```

This is separate from Host recovery. Adding a Host device does not rotate the Host recovery code.

## Clear credential roles

The Server credential model remains:

1. **Bootstrap Key** — `COCKLEBUR_BOOTSTRAP_KEY`, used to claim an unclaimed instance.
2. **Host / project browser sessions** — normal day-to-day access, now explicitly multi-device.
3. **Recovery Code / recovery link** — emergency recovery after access is lost.

Invite, Add device and Recovery now have distinct meanings:

- **Invite** = create a new project person.
- **Add device** = add a browser/device to an existing person.
- **Recovery** = restore access after normal sessions are unavailable.


## Managed in-app updates

The standard Server image now includes a small unprivileged managed-runtime supervisor. After one final normal deployment onto this image, compatible future runtime updates can be applied from **Update center**:

```text
Upload → Validate → Backup → Stage → Apply → Restart → Health check
                                            ↘ automatic code rollback on failure
```

The web process does not receive Docker/Kubernetes credentials or a host shell. The supervisor only switches Cocklebur runtime release slots under the persistent data volume. Managed Runtime v1 rejects updates that change `requirements.txt`; dependency-changing releases still require a normal image deployment.

A server still running 0.2.17.2 or older needs this one-time bootstrap deployment because the old process has no updater executor to run an update package.

## Compatibility

- Existing 0.2.17.x project browser credentials remain valid after upgrade and appear as legacy sessions in the device list until replaced/revoked.
- Existing 0.2.16+ Host state and Host recovery remain compatible.
- The previous hidden eight-session truncation is removed; Cocklebur no longer silently drops older sessions merely because more devices were added.
- Imported Server projects clear browser/device credentials before new access is issued to the importing browser.
- Project Pack format remains **1.0**.

## Retained 0.2.17.x features

- Workspace Bundle export/import and preflight.
- Notes as a Card type.
- Idempotent Card creation and visible Saving state.
- Clean `COCKLEBUR_BOOTSTRAP_KEY` Host lifecycle and break-glass Host reset.
- Managed Update Center with apply/restart/health-check/automatic code rollback.

**Project pack format:** 1.0
