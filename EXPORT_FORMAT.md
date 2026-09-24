# Project Pack Format — 1.0

A project pack is a ZIP snapshot. It is deliberately readable without Cocklebur.

```text
project.zip
├── pack_manifest.json
├── data/
│   ├── manifest.json
│   ├── project.json
│   ├── people.json
│   ├── settings.json
│   ├── files.json
│   ├── cards/
│   ├── discussions/
│   ├── announcements.jsonl
│   └── activity.jsonl
├── readable/
│   ├── overview.txt
│   ├── tasks-and-events.txt
│   ├── announcements.txt
│   ├── files-index.txt
│   └── discussions/*.txt
└── files/
    └── original uploaded files
```

`pack_manifest.json` contains `format`, `format_version`, project identity, export time, source instance identity, and SHA-256 checksums for exported content.

## Import rules

Import validates ZIP paths, required files, format version, and checksums before installing a project. It rejects path traversal and malformed packs. Version `1.0` has a migration hook so future app versions can add explicit migrations instead of silently guessing.

## Canonical-copy rule

An exported pack is a snapshot, not a synchronized writable replica. Importing it creates a new canonical instance in the current deployment. Do not continue editing both the old and restored copies and expect them to merge.


## Server 0.2.17 additions

### Notes

Notes remain ordinary Card JSON under `data/cards/` with `type: "note"`. Human-readable exports additionally include `readable/notes.txt`; `readable/tasks-and-events.txt` keeps its legacy name for pack-format 1.0 compatibility.

### Workspace Bundle 1.0

A Workspace Bundle is only a container of ordinary Project Pack 1.0 ZIPs:

```text
Cocklebur_Workspace_*.zip
├─ bundle-manifest.json
├─ checksums.json
└─ projects/
   ├─ p_....zip
   └─ p_....zip
```

Each nested Project Pack is validated with the normal path/checksum/schema rules before import.
