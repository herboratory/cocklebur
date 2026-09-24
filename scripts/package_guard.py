from __future__ import annotations

import compileall
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    'README.md', 'README_zh-Hant.md', 'DEPLOY_SERVER.md', 'PR2_MERGE_NOTES.md',
    'USER_GUIDE.md', 'USER_GUIDE_zh-Hant.md', 'BACKUP_RESTORE.md',
    'UPDATE.md', 'UPDATE_PACKAGE_FORMAT.md', 'EXPORT_FORMAT.md', 'SECURITY.md', 'LICENSE',
    'CHANGELOG.md', 'RELEASE.md', 'ACCEPTANCE_SERVER_0.2.17_zh-Hant.md', 'Dockerfile', 'docker-compose.yml',
    '.env.example', 'requirements.txt',
    'app/__init__.py', 'app/main.py', 'app/storage.py', 'app/update_center.py',
    'app/static/app.js', 'app/static/app.css', 'app/static/cocklebur-logo.png',
    'app/templates/index.html', 'app/templates/project.html', 'scripts/build_update_package.py', 'scripts/smoke_server_0217.py',
]

FORBIDDEN_FILES = [
    '.env', 'data/.instance_secret', 'data/.instance_id', 'data/.host_key'
]
FORBIDDEN_TOP_LEVEL = [
    'desktop.py', 'build_desktop.py', 'requirements-desktop.txt',
    'INSTALL_LOCAL.md', 'run_local.py', '__MACOSX'
]


def fail(message: str) -> None:
    raise SystemExit(message)


def main() -> None:
    missing = [x for x in REQUIRED if not (ROOT / x).exists()]
    if missing:
        fail('Missing required server release files: ' + ', '.join(missing))
    print('PASS — required server release files present')

    forbidden = [x for x in FORBIDDEN_FILES if (ROOT / x).exists()]
    forbidden += [x for x in FORBIDDEN_TOP_LEVEL if (ROOT / x).exists()]
    if forbidden:
        fail('Forbidden release artifacts present: ' + ', '.join(forbidden))

    caches = []
    for p in ROOT.rglob('*'):
        if p.is_dir() and p.name in {'__pycache__', '.pytest_cache'}:
            caches.append(p)
        elif p.is_file() and (p.suffix in {'.pyc', '.pyo'} or p.name.startswith('._') or p.name == '.DS_Store'):
            caches.append(p)
    if caches:
        fail('Cache/metadata artifacts present: ' + ', '.join(str(p.relative_to(ROOT)) for p in caches[:10]))

    data_root = ROOT / 'data'
    if data_root.exists():
        projects = list(data_root.glob('p_*'))
        if projects:
            fail('Unexpected project data in release: ' + ', '.join(str(p.relative_to(ROOT)) for p in projects[:10]))
    print('PASS — no runtime secrets, project data, or OS cache metadata')

    if not compileall.compile_dir(ROOT / 'app', quiet=1):
        fail('Python compile failed')
    print('PASS — Python syntax')

    if shutil.which('node'):
        result = subprocess.run(['node', '--check', str(ROOT / 'app/static/app.js')], cwd=ROOT)
        if result.returncode:
            fail('JavaScript syntax failed')
        print('PASS — JavaScript syntax')

    release = (ROOT / 'RELEASE.md').read_text('utf-8')
    for marker in ['SERVER-0.2.17-WORKSPACE-NOTE-UPDATE-STAGING', '0.2.17', 'Project pack format:** 1.0']:
        if marker not in release:
            fail(f'Missing release marker: {marker}')

    # compileall creates __pycache__; remove it so a guard run does not dirty the release tree.
    for p in sorted(ROOT.rglob('__pycache__'), key=lambda x: len(x.parts), reverse=True):
        shutil.rmtree(p, ignore_errors=True)
    for p in ROOT.rglob('*.pyc'):
        p.unlink(missing_ok=True)

    print('PASS — package guard complete')


if __name__ == '__main__':
    main()
