# 0.2.17.2 — Host credential cleanup

- Uses one deployment credential name only: `COCKLEBUR_BOOTSTRAP_KEY`.
- Uses a single explicit deployment bootstrap credential with no credential-name fallback.
- Server mode now requires an explicit `COCKLEBUR_BOOTSTRAP_KEY`; missing configuration fails startup clearly.
- Renames the internal setting to `bootstrap_key` and the first-claim endpoint to `/api/host/claim` to match the actual lifecycle.
- Keeps the 0.2.16/0.2.17.1 Host lifecycle: bootstrap claim → browser Host session → rotating Host recovery code.
- Keeps break-glass `python -m app.admin reset-host --yes` and all 0.2.17 functionality.

# 0.2.17.1 — Host recovery hotfix

- Restores the 0.2.16 Instance Host state model (`.instance_auth.json`).
- Restores one-time bootstrap claim, Host recovery, recovery rotation, and multi-browser Host sessions.
- Restored `COCKLEBUR_BOOTSTRAP_KEY` as the bootstrap configuration used by this hotfix line.
- Restores delegated instance Create / Import permissions from 0.2.16.
- Adds `host_claimed` to `/health` and `/api/instance/access`.
- Adds break-glass `python -m app.admin reset-host --yes`, which backs up auth state and preserves project data/grants.
- Adds regression coverage for 0.2.16 Host state → 0.2.17.1 with cleared browser cookies.
- Retains 0.2.17 Workspace Bundle, Note, idempotent Card save, UI spacing, and Update Center staging features.

## 0.2.17 — SERVER-WORKSPACE-NOTE-UPDATE-STAGING

- Added Workspace Bundle export for all Owner/Member projects accessible in the browser, plus multi-pack / Workspace Bundle import preflight and duplicate handling.
- Added retry-safe Card create: Save disables immediately, shows `Saving…`, uses a request timeout, and retries with the same idempotency key so a delayed response cannot create duplicate Cards.
- Added Server Note Cards with stable Card IDs, tags/content, visibility/edit access, and Active/Archived lifecycle.
- Added spacing between Project name and Description in the New Project modal.
- Added Host-only Update Center staging: update ZIP validation, checksum/path safety, version compatibility, pre-update data backup, staging status, and cancel. No Docker/K8s/app replacement authority is granted to the web process.
- Project Pack format remains 1.0.

## 0.2.15-mvp — PW-MVP-01-FINAL

- Finalized the MVP release from the user-validated H16 codebase.
- Preserved the final user-selected typography: Inter / Source Sans 3 / Noto Sans for UI text, and Cormorant Garamond / Noto Serif for display headings.
- Removed the visible footer version label while retaining internal versioning and cache-busting query strings.
- Removed unused footer-version CSS.
- Fixed new project/export manifest metadata to record the current app version instead of the older hard-coded H14 value.
- Release packaging now excludes runtime `.env`, instance secrets/IDs, cache files, and bundled project data.
- Updated release tests and package guard for the final typography and clean-package rules.

## 0.2.14-mvp — PW-MVP-01-H16

- Refined global typography toward the WanderNote editorial style using local/system font stacks only.
- Fixed copy/save toast visibility when a modal dialog backdrop is active.

## 0.2.13-mvp — PW-MVP-01-H15

- Made one-time Member recovery links safe against link previews/prefetch: GET only renders confirmation; POST consumes the token.
- Recovery no longer revokes existing valid browser sessions; Member and Owner identities may have multiple bounded project-scoped browser sessions.
- Owner recovery now preserves existing Owner devices while still rotating the recovery code after successful use.
- Blocked Owner recovery from browsers that already hold a valid project identity, preventing accidental Member→Owner identity replacement.
- Added a human-readable recovery confirmation/error page and clarified recovery UI wording.

## 0.2.12-mvp — PW-MVP-01-H14

- Added Card visibility: `Everyone` or `Only me` (creator-only visibility).
- Kept Card visibility separate from edit access and assignees; assignees do not grant/restrict edit permission.
- Enforced private Card visibility server-side for list/detail/activity/ICS/tags and filtered project activity/unread to avoid leaking private Card activity.
- Only the Card creator can change visibility.
- Added human-readable `Card visibility changed` audit entries.
- Added spacing between the Card Activity heading and activity list in the Card modal.
- Older packs/cards default to `Everyone` visibility.

# Changelog

## 0.2.11-mvp — PW-MVP-01-H13

- Added Server Host access for instance-level Create/Import authorization, separate from project Owner/Member/Viewer roles.
- Added Owner break-glass recovery codes and retained Owner-generated one-time member recovery links.
- Members may create Cards; Viewers are project-content read-only.
- Added Public/Private Card editing and creator-only To-do/Event deletion.
- Added per-Card audit activity including human-readable checklist completion/reopen records with actor snapshots.
- Added self-service display-name editing while keeping role changes Owner-only.
- Hid invitation controls for Local projects and retained Owner recovery data for future Tauri Desktop packaging.
- Normalized older imported packs for H13 identity/card permission fields and grants the importing browser Owner access on Server import.
- User-facing Activities never expose raw event keys such as `card.created`.

## 0.2.10-mvp — PW-MVP-01-H12

- Server import now grants Owner access directly to the importing browser instead of redirecting through an absolute recovery URL.
- Import file input resets so re-selecting the same ZIP triggers a new request/error.
- Added `POPUP_HOST_PORT` for explicit host-port mapping and clarified that `POPUP_BASE_URL` does not change the Docker port.
- Added clean Docker reset documentation and H12 regression coverage.

## 0.2.9-mvp — PW-MVP-01-H11

- Replaced all eight top navigation icons with the exact user-provided SVG assets, in order: Projects, Dashboard, Announcements, Cards, Discussions, Files, Members, Settings.
- Vendored the SVG assets under `app/static/nav-icons/` and render them through CSS masks so active / disabled / hover states keep Cocklebur's existing grayscale theme.
- No backend, data model, deployment, or navigation behavior changes.

## 0.2.8-mvp — PW-MVP-01-H10

- New Project Cancel / close buttons now bypass required-field validation and close immediately.
- Added vertical spacing between the desktop custom-storage row and its immutability guidance.
- Discussion replies now update the expanded thread in place instead of reloading the whole thread list, preserving open state and avoiding collapse/flicker.
- Kept H9 native Save dialog normalization unchanged.

## 0.2.7-mvp — PW-MVP-01-H9

- Fixed desktop native Save dialog path parsing across pywebview backend/version return shapes.
- Prevented the `result[0]` string-indexing bug that could turn `/Users/.../file.ext` into `/`.
- Added regression tests for `.ics`/file/export native-save plumbing and folder selection normalization.

## 0.2.6-mvp — PW-MVP-01-H8

- Clarified macOS `.app` bundles/folders as unsupported direct uploads; users are instructed to compress them to ZIP first.
- Added explicit `.app` package detection when the browser/WebView returns one as a File.
- Added drag-and-drop directory detection through `webkitGetAsEntry` where available.
- Upload validation errors now visually mark the drop zone invalid and scroll the alert into view.
- Added H8 browser regression and focused Local acceptance checklist.

## 0.2.5-mvp — PW-MVP-01-H7

- Fix silent oversized-file upload UX: validate file size before upload.
- Show readable per-file limit and project remaining quota errors.
- Disable Upload while the selected batch is invalid.
- Add writer-accessible upload-limits endpoint and retain backend enforcement.
- Add H7 browser regression and focused Local acceptance checklist.

## 0.2.4-mvp — PW-MVP-01-H6

- Checklist clicks now use local optimistic DOM updates instead of rebuilding Cards / Dashboard accordions.
- Successful checklist saves no longer need scroll restoration, eliminating the visible flash/jump.
- Error/409 paths roll back locally and retain scroll restoration only as a fallback.
- Browser regression now verifies DOM-node identity survives checklist updates.

## 0.2.3-mvp — PW-MVP-01-H5

- Checklist updates now preserve the exact internal scroll position in both Cards and expanded Dashboard To-do/Event panels.
- Scroll restoration waits until Markdown rendering is complete, preventing the content from jumping back toward the top.

## 0.2.2-mvp — PW-MVP-01-H4

- Fixed Dashboard announcement timeline line/dot centering.
- Dashboard checklist updates now preserve the open accordion state.
- Mobile top-navigation icon group now centers when it fits and remains horizontally scrollable when it does not.

# Changelog

## 0.2.1-mvp — PW-MVP-01-H3

- Fixed Assignee multi-select close behavior and raw-ID display.
- Added no-dash checklist parsing, Dashboard checklist rendering, and Card quick status switching.
- Renamed task-facing status labels to Pending / In Progress.
- Added multi-Card file links with backward-compatible file metadata.
- Humanized activity labels, aligned Dashboard timeline dots/line, enlarged the New Card icon, removed top-nav divider, and improved mobile horizontal navigation.
- Added H3 browser regression coverage and Local acceptance checklist.

## 0.2.0-mvp — PW-MVP-01-H2

- Finalized Cocklebur branding and bundled the supplied logo.
- Rebuilt navigation, footer and near-white visual system.
- Reworked Dashboard, timeline Announcements, unified Cards, Discussion filters, Files table/upload, Members settings and Settings tabs.
- Added inline announcement title/tag editing in append-only history.
- Kept project-pack format at 1.0 and preserved existing data compatibility.
- Updated local browser smoke and UI regression tests.

## 0.1.1-mvp — PW-MVP-01-H1

- Reworked the visual system and page hierarchy.
- Replaced Board/List/Calendar Card modes with one responsive Card grid.
- Added inline Card previews and checklist completion.
- Added badge/token tag inputs.
- Reworked Overview around Announcements, Discussion and current Cards.
- Added desktop-native save flow for `.ics`, project exports and file downloads.
- Added Local storage-path display/copy and creation warning.
- Updated tests and human-acceptance map for H1.

## 0.1.0-mvp — PW-MVP-01

Initial complete MVP baseline.

- Portable JSON/JSONL project capsule
- Atomic writes, file locks, consistent snapshot export
- Versioned project-pack format with checksums
- Local and canonical Server modes
- Responsive dashboard/project UI
- Cards: Board/List/Calendar, task/event, tags/assignees/checklists
- `.ics` event export
- Announcements
- Channel/thread Discussion with visibility controls
- File upload/download/metadata/search
- Owner/Member/Viewer roles
- Invite links, QR, optional PIN, secure cookies
- One-time recovery links and last-Owner protection
- Optimistic `409` conflict protection
- Activity/unread cues
- Project quota and upload limit
- Review/export/archive/delete lifecycle
- Local desktop wrapper source + native folder picker bridge
- Docker self-host deployment
- User, security, backup, update, export-format and acceptance documentation
