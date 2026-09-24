# Cocklebur Server User Guide

## 1. Projects and Host access

The Server Host controls whether this Cocklebur instance may create or import projects. Project Owner / Member / Viewer roles do not grant Host access.

After Host access is unlocked, choose **New project** or **Import pack** from Projects.

## 2. Project roles

- **Owner:** project administration, invitations, roles, recovery, export/close/delete.
- **Member:** normal project writing, replies, and uploads.
- **Viewer:** read-only for project content; may still update their own display name.

A project may have multiple Owners. The last Owner cannot be demoted or removed.

## 3. Cards

Cards are To-do or Event items and can contain status, dates, assignees, tags, Markdown content, and checklist items.

### Visibility

- **Everyone:** all project members who otherwise have access to the project can see the Card.
- **Only me:** only the Card creator can see it.

### Edit access

- **Shared:** Owners/Members who can see the Card may edit it.
- **Creator only:** only the Card creator may edit it.

Assignees indicate responsibility and do not change visibility or edit permission.

Delete is always creator-only for both To-do and Event cards.

Card Activity records human-readable history such as who completed/reopened a checklist item or changed content/status/schedule.

## 4. Announcements

Use Announcements for high-signal project-wide notices.

## 5. Discussion

Discussion uses channels, titled threads, and replies. Owners can configure channel visibility for everyone, selected roles, or selected people. Members can participate in channels they can see; Viewers are read-only.

## 6. Files

Upload/download original files with optional metadata and Card links. Cocklebur enforces per-file size and project quota limits and records SHA-256 digest metadata.

Folders and macOS `.app` bundles should be compressed to ZIP before upload.

## 7. Invitations

An Owner generates an invite link/QR. The invited person opens it, enters a display name (and optional PIN), and receives a project-scoped browser credential.

The invitation link is not the person's long-term credential.

## 8. Recovery

If a collaborator loses browser access, an Owner can generate a one-time recovery link for that existing identity.

The link first opens a confirmation page. Recovery is completed only after confirmation, so link previews/prefetch do not consume the token.

Recovery restores that existing identity and does **not** invalidate other valid browser sessions.

Owners also have a break-glass Owner recovery code. A successful Owner recovery rotates the code; save the newly issued code.

## 9. Conflict handling

If two people edit the same mutable entity from the same old version, the later stale save receives a conflict response rather than silently overwriting the newer version.

## 10. Export

**Export current state** creates a consistent ZIP containing:

- `data/` — machine-readable project state
- `readable/` — human-readable text
- `files/` — original uploads

Export is available at any time.

## 11. Closing a project

Owners can review the project, export the current state, then archive or delete the canonical server copy. Permanent deletion requires a current export.

## 12. Restore

Use **Import pack** from Projects after obtaining Host access. The pack is validated before installation. The importing browser receives Owner access and a fresh Owner recovery code.

If the same project ID already exists on the instance, import is rejected instead of silently creating a second writable copy.
