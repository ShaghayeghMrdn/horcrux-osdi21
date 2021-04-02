#!/bin/bash
# set -x

output_dir=$1
if [[ ! -d "$output_dir" ]]; then
    echo "[Error] $output_dir is not a directory"
    exit 1
fi
page_name=$(basename "$output_dir")
mm-webreplay "$output_dir" node chrome.js -u "https://$page_name" -p $((9000 + $RANDOM % 500)) -a