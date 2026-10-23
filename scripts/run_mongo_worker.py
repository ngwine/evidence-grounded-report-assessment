"""Run the authenticated, bounded PARSE worker against the private local replica set."""

from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.backend.src.kltn_ai.api.runtime import connect_from_private_file
from services.backend.src.kltn_ai.worker.mongo_worker import MongoParseWorker


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--uri-file", type=Path, default=ROOT / "var/infra/mongodb/worker_app-uri")
    parser.add_argument("--root", type=Path, default=ROOT / "var/app-mongo")
    parser.add_argument("--owner", default=f"parse-worker-{os.getpid()}")
    parser.add_argument("--once", action="store_true", help="Claim and process at most one PARSE job")
    parser.add_argument("--idle-seconds", type=float, default=1.0)
    parser.add_argument("--max-jobs", type=int, default=100, help="Exit after this many claims; restart externally")
    parser.add_argument("--max-idle-polls", type=int, default=60, help="Exit after consecutive empty polls")
    args = parser.parse_args()
    if (not 0.1 <= args.idle_seconds <= 30 or not 1 <= args.max_jobs <= 10000
            or not 1 <= args.max_idle_polls <= 3600):
        parser.error("Use bounded idle and job limits")
    client = None
    try:
        client, database = connect_from_private_file(args.uri_file, role="kltn_worker")
        worker = MongoParseWorker(database, args.root, owner=args.owner)
        processed = 0
        idle_polls = 0
        while processed < args.max_jobs and idle_polls < args.max_idle_polls:
            claimed = worker.process_one()
            if claimed:
                processed += 1
                idle_polls = 0
            if args.once:
                break
            if not claimed:
                idle_polls += 1
                time.sleep(args.idle_seconds)
        print(f"PARSE worker stopped; processed={processed}")
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception:  # noqa: BLE001 - CLI boundary must not print credentials, filenames or report contents.
        print("PARSE worker could not complete safely; inspect job safe error codes.", file=sys.stderr)
        return 2
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
