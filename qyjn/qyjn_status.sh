#!/bin/sh
cd "$(dirname "$0")"
mkdir -p "$XDG_DATA_HOME/qyjn_status"
ERROR_FILE="$XDG_DATA_HOME/qyjn_status/error.log"
python3 qyjn_status.py 2>"$ERROR_FILE"
