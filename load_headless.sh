#!/bin/bash
# set -x

output_dir=$1
output_dir=${output_dir%%/}
if [[ ! -d "$output_dir" ]]; then
    echo "[Error] $output_dir is not a directory"
    exit 1
fi

for page_dir in $output_dir/*; do
    page_name=$(basename "$page_dir")
    if [[ "$page_name" != "temp" ]]; then
        echo $page_name
        mm-webreplay "$page_dir" node chrome.js -u "https://$page_name" -p $((9000 + $RANDOM % 500))
    fi
done
echo "DONE!"