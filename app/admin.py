from __future__ import annotations

import argparse

from .config import load_settings
from .storage import CapsuleStore


def main() -> None:
    parser = argparse.ArgumentParser(description="Cocklebur Server break-glass administration")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("host-status", help="Show whether the instance Host has been claimed")
    reset = sub.add_parser("reset-host", help="Reset only the instance Host claim; preserve projects and instance grants")
    reset.add_argument("--yes", action="store_true", help="Confirm the destructive Host credential reset")
    args = parser.parse_args()

    settings = load_settings()
    store = CapsuleStore(settings)

    if args.command == "host-status":
        print(f"data_dir={settings.data_dir}")
        print(f"host_claimed={str(store.host_claimed()).lower()}")
        return

    if args.command == "reset-host":
        if not args.yes:
            raise SystemExit(
                "Refusing to reset Host without --yes. This invalidates current Host sessions/recovery, "
                "but preserves projects and instance grants."
            )
        backup = store.reset_host_claim()
        if backup:
            print("Host claim reset.")
            print(f"Backup: {backup}")
        else:
            print("No instance Host state existed; instance is already unclaimed.")
        print("Projects preserved: yes")
        print("Instance grants preserved: yes")
        print("Next: restart Cocklebur if needed, then Claim Host with the configured bootstrap key.")


if __name__ == "__main__":
    main()
