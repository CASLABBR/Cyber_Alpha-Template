#!/usr/bin/env bash
set -euo pipefail
source_dir=${1:?source ausente}
output_dir=${2:?output ausente}
product=${3:?produto ausente}
version=${4:?versao ausente}
safe_product=$(printf '%s' "$product" | tr -cs 'A-Za-z0-9._-' '-')
site_dir="$output_dir/${safe_product}-${version}-Site"
mkdir -p "$site_dir"
tar -C "$source_dir" --exclude=.git --exclude=.github --exclude=node_modules -cf - . | tar -C "$site_dir" -xf -
cat > "$site_dir/Abrir-Site.cmd" <<'EOF'
@echo off
cd /d "%~dp0"
start "" index.html
EOF
printf '%s\n' "$safe_product $version" 'Site portatil: abra Abrir-Site.cmd ou index.html.' > "$site_dir/LEIA-ME.txt"
(cd "$site_dir" && find . -type f ! -name SHA256SUMS.txt -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS.txt)
(cd "$output_dir" && zip -qr "${safe_product}-${version}-Site.zip" "$(basename "$site_dir")")
