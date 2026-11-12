"""Inspect mapping decisions or validate one frozen dataset pack."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .registry import load_registry, validate_pack_manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("list", help="Show mapping decisions, not run permissions")
    check = subcommands.add_parser("check", help="Validate one approved frozen pack")
    check.add_argument("manifest", type=Path)
    check.add_argument("--purpose", required=True)
    args = parser.parse_args()
    if args.command == "list":
        registry = load_registry()
        for entry in registry["datasets"]:
            print(
                f"{entry['id']}: mapping={entry['mapping']['decision']} "
                f"rights-in-workbook={entry['rights']['workbook_status']}"
            )
        return 0
    try:
        result = validate_pack_manifest(args.manifest, args.purpose)
    except (OSError, ValueError, json.JSONDecodeError) as error:
        parser.exit(2, f"DENIED: {error}\n")
    print(json.dumps({"result": "APPROVED_PACK", **result}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
