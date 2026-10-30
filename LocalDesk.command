#!/bin/sh
set -eu
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
[ -x "$project_dir/.venv/bin/python" ] || { echo 'Run scripts/install.sh first.' >&2; exit 1; }
exec "$project_dir/.venv/bin/python" "$project_dir/app/launch_assistant.py" "$@"
