# Release

- **Release ID:** SERVER-INSTANCE-AUTH-01
- **Version:** 0.2.16
- **Project pack format:** 1.0
- **Distribution:** Docker/self-hosted Server

## Scope

- One-time Host bootstrap claim backed by persistent instance auth state.
- Host recovery code with rotation and multi-browser Host sessions.
- Host is instance-level and remains separate from project Owner / Member / Viewer.
- Independent delegated instance permissions: Create projects / Import project packs.
- Create/Import grants attach to an existing project identity and do not change that project's role.
- Project creator/importer receives Owner access to the newly created/imported project.
- Removing a project identity or deleting its source project removes associated delegated grants.
- Infrastructure Admin / Deployer remains outside Cocklebur app roles.
- Project pack format stays at 1.0; instance auth/grants are not exported with project packs.
