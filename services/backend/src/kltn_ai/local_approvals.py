"""Explicit checksum approval for sources used in private localhost tests.

An approval here is *not* a statement that a public dataset license is cleared.
Only an operator who checked the material's local-use rights should run this.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from services.backend.src.kltn_ai.local_store import LocalStore, sha256_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=None, help="Private local state directory")
    subcommands = parser.add_subparsers(dest="command", required=True)
    approve = subcommands.add_parser("approve-source", help="Approve exact bytes for private-local processing")
    approve.add_argument("file", type=Path)
    approve.add_argument("--approver", required=True)
    approve.add_argument("--rationale", required=True)
    approve.add_argument("--attest-rights", action="store_true", required=True)
    verify = subcommands.add_parser("check-source", help="Check whether exact bytes have local approval")
    verify.add_argument("file", type=Path)
    args = parser.parse_args(argv)
    store = LocalStore(args.root)
    if args.command == "approve-source":
        record = store.approve_source(
            args.file,
            approver=args.approver,
            rationale=args.rationale,
        )
        print(json.dumps(record, ensure_ascii=False, indent=2))
        return 0
    digest = sha256_path(args.file)
    approved = store.source_is_approved(digest)
    print(json.dumps({"sha256": digest, "approved_for_private_local_test": approved}))
    return 0 if approved else 1


if __name__ == "__main__":
    raise SystemExit(main())
