#!/usr/bin/env bash
set -euo pipefail

source_dir=${1:?uso: package-docker.sh SOURCE OUTPUT PRODUCT VERSION [COMPOSE_FILE]}
output_dir=${2:?output ausente}
product=${3:?produto ausente}
version=${4:?versao ausente}
compose_file=${5:-}
safe_product=$(printf '%s' "$product" | tr -cs 'A-Za-z0-9._-' '-')
mkdir -p "$output_dir/docker-package"

if [[ -n "$compose_file" ]]; then
  (cd "$source_dir" && docker compose -f "$compose_file" config --quiet)
  cp "$source_dir/$compose_file" "$output_dir/docker-package/compose.yaml"
  (cd "$source_dir" && docker compose -f "$compose_file" build)
  (cd "$source_dir" && docker compose -f "$compose_file" images --format json) > "$output_dir/docker-package/images.json" || true
else
  image="autopack/${safe_product,,}:$version"
  docker build \
    --label "org.opencontainers.image.title=$product" \
    --label "org.opencontainers.image.version=$version" \
    --label "org.opencontainers.image.created=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    -t "$image" "$source_dir"
  docker image inspect "$image" > "$output_dir/docker-package/image-inspect.json"
  docker save "$image" | gzip -9 > "$output_dir/docker-package/${safe_product}-${version}.image.tar.gz"
  cat > "$output_dir/docker-package/compose.yaml" <<EOF
services:
  application:
    image: $image
    restart: unless-stopped
EOF
fi

cat > "$output_dir/docker-package/Iniciar.cmd" <<'EOF'
@echo off
cd /d "%~dp0"
where docker >nul 2>nul || (echo Docker Desktop nao encontrado.& pause & exit /b 1)
docker compose up -d --build
if errorlevel 1 pause
EOF
cat > "$output_dir/docker-package/Parar.cmd" <<'EOF'
@echo off
cd /d "%~dp0"
docker compose down
if errorlevel 1 pause
EOF
cat > "$output_dir/docker-package/Ver-Logs.cmd" <<'EOF'
@echo off
cd /d "%~dp0"
docker compose logs -f --tail=200
EOF
(cd "$output_dir/docker-package" && sha256sum ./* > SHA256SUMS.txt)
tar -C "$output_dir" -czf "$output_dir/${safe_product}-${version}-Docker.tar.gz" docker-package

