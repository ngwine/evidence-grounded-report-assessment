#!/usr/bin/env bash
set -euo pipefail
install -m 400 -o mongodb -g mongodb /run/secrets/replica_key /tmp/kltn-replica-key
# The official entrypoint drops root before resolving *_FILE. Linux Compose
# bind-mounted secrets retain the host's 0600 ownership; mongodb cannot read
# them directly. Copy to the private tmpfs with the runtime UID, never chmod
# the host files or expose credentials as command-line arguments.
install -m 400 -o mongodb -g mongodb /run/secrets/root_user /tmp/kltn-root-user
install -m 400 -o mongodb -g mongodb /run/secrets/root_password /tmp/kltn-root-password
export MONGO_INITDB_ROOT_USERNAME_FILE=/tmp/kltn-root-user
export MONGO_INITDB_ROOT_PASSWORD_FILE=/tmp/kltn-root-password
exec /usr/local/bin/docker-entrypoint.sh mongod \
  --replSet kltn-rs --bind_ip_all --keyFile /tmp/kltn-replica-key \
  --wiredTigerCacheSizeGB 0.25
