#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)

if [ -x /usr/share/klippy-env/bin/python ]; then
    PY=/usr/share/klippy-env/bin/python
elif command -v python3 >/dev/null 2>&1; then
    PY=python3
else
    echo "ERROR: Python 3 was not found." >&2
    exit 1
fi

exec "$PY" "$SCRIPT_DIR/scripts/k1max_cfs_eddy.py" "$@"
