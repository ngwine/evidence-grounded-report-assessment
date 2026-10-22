#!/usr/bin/env bash
set -euo pipefail
install -m 400 -o mongodb -g mongodb /run/secrets/replica_key /tmp/kltn-replica-key
exec /usr/local/bin/docker-entrypoint.sh mongod \
  --replSet kltn-rs --bind_ip_all --keyFile /tmp/kltn-replica-key \
  --wiredTigerCacheSizeGB 0.25
