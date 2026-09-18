# Cocklebur Server User Guide

## 1. Instance access vs project roles

Cocklebur has two different authorization scopes.

**Instance:** Host, Create projects, Import project packs.  
**Project:** Owner, Member, Viewer.

A project role never automatically grants instance Create/Import.

## 2. Host

Host administers the Cocklebur instance and always has Create + Import. Host can also grant or remove Create / Import independently for existing project identities from **Projects → Instance permissions**.

Host is not automatically Owner of every project and should not be treated as a universal project reader.

## 3. Project roles

- **Owner:** project administration, invitations, roles, recovery, export/close/delete.
- **Member:** normal writing, replies, Cards, and uploads.
- **Viewer:** read-only for project content; may update their own display name.

A project may have multiple Owners. The last Owner cannot be demoted or removed.

## 4. Create / Import delegation

A Member, Viewer, or Owner may additionally receive:

- **Create projects** — New project becomes available; creator becomes Owner of the new project.
- **Import project packs** — Import becomes available; importing browser receives Owner access to the imported project.

These capabilities do not change the person's role in existing projects.

## 5. Invitations and recovery

Owner-generated invitations create project-scoped browser access. Collaborator recovery restores the same project identity and preserves other valid browser sessions.

Owners also have a rotating break-glass Owner recovery code.

Host recovery is separate from Owner recovery. After first Host claim, the deployment bootstrap key is disabled as a Host login method; use the current Host recovery code on another browser.

## 6. Cards, Discussion, Files and Export

Cards support visibility, shared/creator-only edit access, tags, assignees, dates, checklists and audit history. Discussion uses channels and titled threads. Files keep original uploads plus metadata. Export produces a portable project pack containing structured data, readable text and original files.
