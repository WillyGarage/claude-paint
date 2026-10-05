#!/usr/bin/env bash
# Keep a static copy of the studio viewer (studio/export_static.py) somewhere a phone can open it:
# export every painter on this machine (Claude Code painters included) and rsync the export to <dest>,
# once a minute.
#
#   harness/claude-code/publish_studio.sh <rsync-dest> [seconds]     e.g. host:~/www/studio/
#
# The export folder is PUBLISH_DIR (default ~/paint-studios/.studio-site). Open <dest's URL>/?p=<studio>.
set -uo pipefail
dest=${1:?usage: publish_studio.sh <rsync-dest> [seconds]}
every=${2:-60}
repo=$(cd "$(dirname "$0")/../.." && pwd)
out=${PUBLISH_DIR:-$HOME/paint-studios/.studio-site}
while true; do
  if uv run --quiet "$repo/studio/export_static.py" "$out" >/dev/null; then
    rsync -a --delete --exclude .studio-export "$out/" "$dest" || echo "$(date '+%F %T') rsync failed" >&2
  else
    echo "$(date '+%F %T') export failed" >&2
  fi
  sleep "$every"
done
