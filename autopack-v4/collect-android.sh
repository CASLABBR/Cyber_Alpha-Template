#!/usr/bin/env bash
set -euo pipefail

source_dir=${1:?source ausente}
output_dir=${2:?output ausente}
product=${3:?produto ausente}
version=${4:?versao ausente}

safe_label() {
  local value=$1 label=$2
  [[ $value =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$ && $value != '.' && $value != '..' ]] || {
    echo "$label inseguro: $value" >&2
    exit 2
  }
}

sanitize_identifier() {
  local value=$1
  value=${value//\\//}
  value=${value//\//-}
  value=$(printf '%s' "$value" | LC_ALL=C sed -E 's/[^A-Za-z0-9._-]+/-/g; s/-+/-/g; s/^[.-]+//; s/[.-]+$//')
  [[ -n $value ]] || value=artifact
  printf '%s' "$value"
}

json_escape() {
  local value=$1
  value=${value//\\/\\\\}
  value=${value//\"/\\\"}
  value=${value//$'\n'/\\n}
  value=${value//$'\r'/\\r}
  value=${value//$'\t'/\\t}
  printf '%s' "$value"
}

safe_label "$product" produto
safe_label "$version" versao
[[ -d $source_dir ]] || { echo "Diretorio fonte inexistente: $source_dir" >&2; exit 2; }
mkdir -p "$output_dir"

source_abs=$(cd "$source_dir" && pwd -P)
output_abs=$(cd "$output_dir" && pwd -P)

# Links in Gradle output trees are rejected rather than followed or silently
# omitted.  This prevents an artifact from escaping the checked-out project.
if find "$source_abs" -path '*/build/outputs/*' -type l -print -quit | grep -q .; then
  echo 'Links simbolicos nao sao permitidos em build/outputs.' >&2
  exit 3
fi

mapfile -d '' artifacts < <(
  find "$source_abs" -type f \( \
    -path '*/build/outputs/apk/*.apk' -o \
    -path '*/build/outputs/apk/*/*.apk' -o \
    -path '*/build/outputs/apk/*/*/*.apk' -o \
    -path '*/build/outputs/bundle/*.aab' -o \
    -path '*/build/outputs/bundle/*/*.aab' -o \
    -path '*/build/outputs/bundle/*/*/*.aab' \
  \) -print0 | sort -z
)
((${#artifacts[@]})) || { echo 'Nenhum APK ou AAB produzido.' >&2; exit 1; }

declare -A destinations=()
declare -a inventory_source=() inventory_name=() inventory_kind=() inventory_size=() inventory_hash=()

for file in "${artifacts[@]}"; do
  [[ ! -L $file ]] || { echo "Link simbolico recusado: $file" >&2; exit 3; }
  relative=${file#"$source_abs"/}
  [[ $relative != "$file" && $relative != *$'\n'* && $relative != *$'\r'* ]] || {
    echo "Caminho de artefato inseguro: $relative" >&2
    exit 3
  }
  extension=${file##*.}
  kind=${extension^^}
  identifier=${relative%.*}
  identifier=$(sanitize_identifier "$identifier")
  destination_name="${product}-${version}-${identifier}.${extension,,}"
  collision_key=${destination_name,,}
  if [[ -n ${destinations[$collision_key]+x} ]]; then
    echo "Colisao de artefatos: ${destinations[$collision_key]} e $relative -> $destination_name" >&2
    exit 4
  fi
  destinations[$collision_key]=$relative
  destination="$output_abs/$destination_name"
  cp -- "$file" "$destination"
  digest=$(sha256sum -- "$destination" | cut -d ' ' -f1)
  size=$(wc -c < "$destination" | tr -d '[:space:]')
  inventory_source+=("$relative")
  inventory_name+=("$destination_name")
  inventory_kind+=("$kind")
  inventory_size+=("$size")
  inventory_hash+=("$digest")
done

(
  cd "$output_abs"
  printf '%s\0' "${inventory_name[@]}" | sort -z | xargs -0 sha256sum -- > SHA256SUMS.txt
)

inventory="$output_abs/android-artifacts.json"
{
  printf '{\n  "schema": "https://caslabbr.github.io/autopack/android-artifacts/v1",\n'
  printf '  "product": "%s",\n  "version": "%s",\n  "artifacts": [\n' \
    "$(json_escape "$product")" "$(json_escape "$version")"
  for ((index=0; index<${#inventory_name[@]}; index++)); do
    (( index == 0 )) || printf ',\n'
    printf '    {"file": "%s", "source": "%s", "kind": "%s", "bytes": %s, "sha256": "%s"}' \
      "$(json_escape "${inventory_name[$index]}")" \
      "$(json_escape "${inventory_source[$index]}")" \
      "${inventory_kind[$index]}" \
      "${inventory_size[$index]}" \
      "${inventory_hash[$index]}"
  done
  printf '\n  ]\n}\n'
} > "$inventory"

printf 'Coletados %d artefatos Android em %s\n' "${#inventory_name[@]}" "$output_abs"
