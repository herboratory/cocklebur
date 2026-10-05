from __future__ import annotations

import compileall
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = [
    'README.md', 'README_zh-Hant.md', 'DEPLOY_SERVER.md', 'DEPLOY_0.2.18.1_zh-Hant.md',
    'HOST_ACCESS_0.2.18.1.md', 'MULTI_DEVICE_ACCESS_0.2.18.1.md', 'MANAGED_UPDATES_0.2.18.1.md',
    'USER_GUIDE.md', 'USER_GUIDE_zh-Hant.md', 'BACKUP_RESTORE.md',
    'UPDATE.md', 'UPDATE_PACKAGE_FORMAT.md', 'EXPORT_FORMAT.md', 'SECURITY.md', 'LICENSE',
    'CHANGELOG.md', 'RELEASE.md', 'ACCEPTANCE_SERVER_0.2.18.1_zh-Hant.md', 'Dockerfile', 'docker-compose.yml',
    '.env.example', 'requirements.txt',
    'app/__init__.py', 'app/main.py', 'app/storage.py', 'app/update_center.py', 'app/admin.py', 'bootstrap/supervisor.py',
    'app/static/app.js', 'app/static/app.css', 'app/static/cocklebur-logo.png',
    'app/templates/index.html', 'app/templates/project.html', 'app/templates/device_link.html',
    'scripts/build_update_package.py', 'scripts/smoke_server_0218.py', 'scripts/smoke_server_0218_regression.py',
    'scripts/test_upgrade_0216_host_to_0218.py', 'scripts/test_bootstrap_key_contract_0218.py', 'scripts/smoke_managed_updater_02181.py',
]
FORBIDDEN_FILES = ['.env', 'data/.instance_secret', 'data/.instance_id', 'data/.host_key', 'data/.instance_auth.json']
FORBIDDEN_TOP_LEVEL = ['desktop.py', 'build_desktop.py', 'requirements-desktop.txt', 'INSTALL_LOCAL.md', 'run_local.py', '__MACOSX']
FORBIDDEN_TEXT = ['COCKLEBUR_' + 'HOST_KEY']


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
        elif p.is_file() and (p.suffix in {'.pyc', '.pyo'} or p.name.startswith('._') or p.name == '.DS_Store' or p.name.endswith('.pre0218')):
            caches.append(p)
    if caches:
        fail('Cache/metadata artifacts present: ' + ', '.join(str(p.relative_to(ROOT)) for p in caches[:10]))

    data_root = ROOT / 'data'
    if data_root.exists() and list(data_root.glob('p_*')):
        fail('Unexpected project data in release')
    print('PASS — no runtime secrets, project data, or OS cache metadata')

    for path in [ROOT / 'app', ROOT / '.env.example', ROOT / 'README.md', ROOT / 'README_zh-Hant.md', ROOT / 'RELEASE.md', ROOT / 'DEPLOY_SERVER.md']:
        items = path.rglob('*') if path.is_dir() else [path]
        for item in items:
            if not item.is_file() or item.suffix.lower() in {'.png', '.jpg', '.jpeg', '.gif', '.ico'}:
                continue
            text = item.read_text('utf-8', errors='ignore')
            for marker in FORBIDDEN_TEXT:
                if marker in text:
                    fail(f'Legacy credential name found in {item.relative_to(ROOT)}: {marker}')
    print('PASS — clean Host credential terminology')

    if not compileall.compile_dir(ROOT / 'app', quiet=1):
        fail('Python compile failed')
    print('PASS — Python syntax')

    if shutil.which('node'):
        result = subprocess.run(['node', '--check', str(ROOT / 'app/static/app.js')], cwd=ROOT)
        if result.returncode:
            fail('JavaScript syntax failed')
        print('PASS — JavaScript syntax')

    release = (ROOT / 'RELEASE.md').read_text('utf-8')
    for marker in ['SERVER-0.2.18.1-MANAGED-UPDATES', '0.2.18.1', 'Project pack format:** 1.0', 'Managed in-app updates']:
        if marker not in release:
            fail(f'Missing release marker: {marker}')

    js = (ROOT / 'app/static/app.js').read_text('utf-8')
    for marker in ['Manage devices', 'Add another device', 'Manage Host devices']:
        if marker not in js:
            fail(f'Missing multi-device UI marker: {marker}')


    update_py = (ROOT / 'app/update_center.py').read_text('utf-8')
    for marker in ['managed-runtime-v1', 'request_apply', 'apply-request.json']:
        if marker not in update_py:
            fail(f'Missing managed updater marker: {marker}')

    supervisor = (ROOT / 'bootstrap/supervisor.py').read_text('utf-8')
    for marker in ['atomic_switch_release', 'wait_health', 'rolled_back']:
        if marker not in supervisor:
            fail(f'Missing supervisor marker: {marker}')

    dockerfile = (ROOT / 'Dockerfile').read_text('utf-8')
    if 'bootstrap/supervisor.py' not in dockerfile or 'COCKLEBUR_MANAGED_RUNTIME=1' not in dockerfile:
        fail('Docker image is not wired to the managed updater supervisor')

    main_py = (ROOT / 'app/main.py').read_text('utf-8')
    for marker in ['/api/host/device-link', '/me/device-link', '/device-link/{project_id}']:
        if marker not in main_py:
            fail(f'Missing multi-device route marker: {marker}')

    for p in sorted(ROOT.rglob('__pycache__'), key=lambda x: len(x.parts), reverse=True):
        shutil.rmtree(p, ignore_errors=True)
    for p in ROOT.rglob('*.pyc'):
        p.unlink(missing_ok=True)

    print('PASS — package guard complete')


if __name__ == '__main__':
    main()
