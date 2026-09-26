from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run_case(env_updates: dict[str, str | None]) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT)
    env["POPUP_APP_MODE"] = "server"
    with tempfile.TemporaryDirectory(prefix="cocklebur_02172_bootstrap_") as td:
        data_dir = Path(td) / "data"
        env["POPUP_DATA_DIR"] = str(data_dir)
        for key, value in env_updates.items():
            if value is None:
                env.pop(key, None)
            else:
                env[key] = value
        proc = subprocess.run(
            [sys.executable, "-c", "from app.config import load_settings; s=load_settings(); print(s.bootstrap_key)"],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
        )
        assert not (data_dir / ".host_key").exists(), "runtime must not generate .host_key"
        return proc


def main() -> None:
    good = run_case({"COCKLEBUR_BOOTSTRAP_KEY": "bootstrap-only"})
    assert good.returncode == 0, good.stderr
    assert good.stdout.strip() == "bootstrap-only"

    missing = run_case({"COCKLEBUR_BOOTSTRAP_KEY": None})
    assert missing.returncode != 0
    assert "COCKLEBUR_BOOTSTRAP_KEY is required" in missing.stderr

    print("PASS — Cocklebur Server 0.2.17.2 bootstrap key contract")


if __name__ == "__main__":
    main()
