#!/bin/sh
cd "$(dirname "$0")"
ERROR_FILE="$XDG_DATA_HOME/qyjn_status/error.log"
python3 qyjn_status.py 2>"$ERROR_FILE"
