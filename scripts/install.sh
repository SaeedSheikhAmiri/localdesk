#!/bin/sh
set -eu
[ "$(uname -s)" = Darwin ] || { echo 'This preview supports macOS only.' >&2; exit 1; }
project_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$project_dir"
python_bin=${PYTHON:-python3.12}
"$python_bin" -c 'import sys; assert sys.version_info >= (3,12), "Python 3.12+ required"'
"$python_bin" -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
printf '%s\n' 'Dependencies installed. Install/start Ollama separately; see README.'
