#!/usr/bin/env bash
set -euo pipefail
source_dir=${1:?source ausente}
output_dir=${2:?output ausente}
product=${3:?produto ausente}
version=${4:?versao ausente}
mkdir -p "$output_dir"
mapfile -d '' artifacts < <(find "$source_dir" -type f \( -path '*/build/outputs/apk/*.apk' -o -path '*/build/outputs/apk/*/*.apk' -o -path '*/build/outputs/bundle/*/*.aab' \) -print0)
((${#artifacts[@]})) || { echo 'Nenhum APK ou AAB produzido.' >&2; exit 1; }
for file in "${artifacts[@]}"; do
  variant=$(basename "$(dirname "$file")")
  extension=${file##*.}
  cp "$file" "$output_dir/${product}-${version}-${variant}.${extension}"
done
(cd "$output_dir" && find . -maxdepth 1 -type f \( -name '*.apk' -o -name '*.aab' \) -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS.txt)

