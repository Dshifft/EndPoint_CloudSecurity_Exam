#!/bin/sh

set -eu
umask 077

backup_directory="/backups"
backup_file="${backup_directory}/banking_db_$(date -u +%Y%m%dT%H%M%SZ).dump"

mkdir -p "${backup_directory}"
pg_dump --format=custom --file="${backup_file}"
# Remove dumps once they are five days old.
find "${backup_directory}" -type f -name '*.dump' -mtime +4 -delete
