#!/usr/bin/env bash
set -euo pipefail
source_dir=${1:?source ausente}
output_dir=${2:?output ausente}
product=${3:?produto ausente}
version=${4:?versao ausente}
safe_product=$(printf '%s' "$product" | tr -cs 'A-Za-z0-9._-' '-')
package_dir="$output_dir/${safe_product}-${version}-Node"
mkdir -p "$package_dir"

# Preserve the runnable project and its installed production dependencies.
tar -C "$source_dir" --exclude=.git --exclude=.github --exclude=node_modules --exclude=dist --exclude=build -cf - . | tar -C "$package_dir" -xf -
if [[ -f "$source_dir/package-lock.json" ]]; then
  (cd "$package_dir" && npm ci --omit=dev --ignore-scripts)
else
  (cd "$package_dir" && npm install --omit=dev --ignore-scripts)
fi

cat > "$package_dir/Iniciar.cmd" <<'EOF'
@echo off
setlocal
cd /d "%~dp0"
where node >nul 2>nul || (echo Node.js nao encontrado. Instale em https://nodejs.org/& pause & exit /b 1)
npm start -- %*
if errorlevel 1 pause
EOF
cat > "$package_dir/Iniciar.sh" <<'EOF'
#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
exec npm start -- "$@"
EOF
chmod +x "$package_dir/Iniciar.sh"
printf '%s\n' "$safe_product $version" 'Pacote Node.js com dependencias de producao incluidas.' > "$package_dir/LEIA-ME.txt"
(cd "$package_dir" && find . -type f ! -name SHA256SUMS.txt -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS.txt)
tar -C "$output_dir" -czf "$output_dir/${safe_product}-${version}-Node.tar.gz" "$(basename "$package_dir")"
