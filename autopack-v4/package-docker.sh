#!/usr/bin/env bash
set -euo pipefail

source_dir=${1:?uso: package-docker.sh SOURCE OUTPUT PRODUCT VERSION [COMPOSE_FILE]}
output_dir=${2:?output ausente}
product=${3:?produto ausente}
version=${4:?versao ausente}
compose_file=${5:-}
command -v docker >/dev/null || { echo 'docker nao encontrado' >&2; exit 1; }
command -v python3 >/dev/null || { echo 'python3 nao encontrado' >&2; exit 1; }
AUTOPACK_DOCKER_BIN=${AUTOPACK_DOCKER_BIN:-docker}
export AUTOPACK_DOCKER_BIN
source_root=$(realpath -e -- "$source_dir")
[[ -d "$source_root" ]] || { echo 'Diretorio de origem invalido' >&2; exit 1; }
safe_product=$(printf '%s' "$product" | tr -cs 'A-Za-z0-9._-' '-' | sed 's/^[.-]*//;s/[.-]*$//')
[[ -n "$safe_product" ]] || safe_product=AutoPack-Application
[[ "$version" =~ ^[A-Za-z0-9][A-Za-z0-9._+-]{0,79}$ ]] || { echo 'Versao insegura' >&2; exit 1; }
package_root="$output_dir/docker-package"
mkdir -p "$package_root"

if [[ -n "$compose_file" ]]; then
  compose_path=$(realpath -e -- "$source_root/$compose_file") || { echo 'Compose inexistente' >&2; exit 1; }
  [[ "$compose_path" == "$source_root/"* && -f "$compose_path" && ! -L "$compose_path" ]] || {
    echo 'Compose deve ser um arquivo regular dentro da origem' >&2; exit 1;
  }
  compose_dir=$(dirname "$compose_path")
  config_json="$package_root/compose-resolved.json"
  docker compose -f "$compose_path" config --format json > "$config_json"

  python3 - "$config_json" "$source_root" "$compose_dir" <<'PY'
import json, pathlib, sys
config_path, source_raw, compose_raw = sys.argv[1:]
config = json.loads(pathlib.Path(config_path).read_text(encoding="utf-8"))
source = pathlib.Path(source_raw).resolve(strict=True)
compose_dir = pathlib.Path(compose_raw).resolve(strict=True)

def inside(path, label, directory=False):
    try:
        resolved = pathlib.Path(path).resolve(strict=True)
        resolved.relative_to(source)
    except (OSError, ValueError) as exc:
        raise SystemExit(f"{label} fora da raiz do projeto: {path}") from exc
    if directory and not resolved.is_dir():
        raise SystemExit(f"{label} nao e diretorio: {resolved}")
    return resolved

for name, secret in (config.get("secrets") or {}).items():
    if not isinstance(secret, dict) or secret.get("external"):
        raise SystemExit(f"secret externo nao permitido: {name}")
    raise SystemExit(f"secret local nao pode ser incorporado ao pacote: {name}")

for service_name, service in (config.get("services") or {}).items():
    build = service.get("build")
    if build:
        build = {"context": build} if isinstance(build, str) else build
        if build.get("additional_contexts"):
            raise SystemExit(f"additional_contexts nao permitido em {service_name}")
        if build.get("entitlements"):
            raise SystemExit(f"entitlements nao permitido em {service_name}")
        if build.get("secrets"):
            raise SystemExit(f"build secrets nao permitidos em {service_name}")
        context_raw = str(build.get("context") or ".")
        if "://" in context_raw or context_raw.startswith(("git@", "docker-image://")):
            raise SystemExit(f"contexto remoto nao permitido em {service_name}")
        context = pathlib.Path(context_raw)
        if not context.is_absolute(): context = compose_dir / context
        context = inside(context, f"build context de {service_name}", True)
        dockerfile = pathlib.Path(str(build.get("dockerfile") or "Dockerfile"))
        if not dockerfile.is_absolute(): dockerfile = context / dockerfile
        dockerfile = inside(dockerfile, f"dockerfile de {service_name}")
        if not dockerfile.is_file():
            raise SystemExit(f"dockerfile invalido em {service_name}: {dockerfile}")
    if service.get("secrets"):
        raise SystemExit(f"runtime secrets nao permitidos em {service_name}")
    for volume in service.get("volumes") or []:
        if isinstance(volume, dict) and volume.get("type") == "bind":
            raise SystemExit(f"bind mount nao portatil em {service_name}")
PY

  docker compose -f "$compose_path" config --quiet
  docker compose -f "$compose_path" build
  images_json="$package_root/images-raw.json"
  docker compose -f "$compose_path" images --format json > "$images_json"
  mapfile -t images < <(python3 - "$images_json" <<'PY'
import json, pathlib, sys
text = pathlib.Path(sys.argv[1]).read_text(encoding="utf-8").strip()
if not text: raise SystemExit("Compose nao produziu imagens")
try:
    parsed = json.loads(text); rows = parsed if isinstance(parsed, list) else [parsed]
except json.JSONDecodeError:
    rows = [json.loads(line) for line in text.splitlines() if line.strip()]
seen = set()
for row in rows:
    repo, tag = row.get("Repository", ""), row.get("Tag", "")
    image = f"{repo}:{tag}" if repo and tag and tag != "<none>" else row.get("ID", "")
    if not image or image.startswith("-") or any(c.isspace() for c in image):
        raise SystemExit(f"Referencia de imagem insegura: {image!r}")
    if image not in seen: print(image); seen.add(image)
if not seen: raise SystemExit("Compose nao produziu referencias de imagem")
PY
  )
  ((${#images[@]})) || { echo 'Compose nao produziu imagens exportaveis' >&2; exit 1; }
  docker save "${images[@]}" | gzip -9 > "$package_root/images.tar.gz"
  [[ -s "$package_root/images.tar.gz" ]] || { echo 'docker save produziu arquivo vazio' >&2; exit 1; }

  python3 - "$config_json" "$images_json" "$package_root/compose.yaml" "$package_root/images.json" <<'PY'
import json, os, pathlib, subprocess, sys
config_path, rows_path, compose_out, inventory_out = map(pathlib.Path, sys.argv[1:])
config = json.loads(config_path.read_text(encoding="utf-8"))
text = rows_path.read_text(encoding="utf-8").strip()
try:
    parsed = json.loads(text); rows = parsed if isinstance(parsed, list) else [parsed]
except json.JSONDecodeError:
    rows = [json.loads(line) for line in text.splitlines() if line.strip()]
by_service, inventory = {}, []
for row in rows:
    repo, tag = row.get("Repository", ""), row.get("Tag", "")
    image = f"{repo}:{tag}" if repo and tag and tag != "<none>" else row.get("ID", "")
    service = row.get("Service", "")
    if service and image: by_service[service] = image
    if image:
        inspect = json.loads(subprocess.check_output([os.environ["AUTOPACK_DOCKER_BIN"], "image", "inspect", image], text=True))[0]
        inventory.append({"service": service, "reference": image, "id": inspect.get("Id", ""),
                          "repo_digests": inspect.get("RepoDigests") or []})
for name, service in (config.get("services") or {}).items():
    if name in by_service: service["image"] = by_service[name]
    service.pop("build", None)
config.pop("name", None)
compose_out.write_text(json.dumps(config, indent=2, sort_keys=True) + "\n", encoding="utf-8")
inventory_out.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")
PY
  rm -f "$config_json" "$images_json"
else
  image="autopack/${safe_product,,}:$version"
  docker build --label "org.opencontainers.image.title=$product" \
    --label "org.opencontainers.image.version=$version" \
    --label "org.opencontainers.image.created=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    -t "$image" "$source_root"
  docker image inspect "$image" > "$package_root/images.json"
  docker save "$image" | gzip -9 > "$package_root/images.tar.gz"
  [[ -s "$package_root/images.tar.gz" ]] || { echo 'docker save produziu arquivo vazio' >&2; exit 1; }
  cat > "$package_root/compose.yaml" <<EOF
services:
  application:
    image: $image
    restart: unless-stopped
EOF
fi

cat > "$package_root/Carregar-Imagens.sh" <<'EOF'
#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
gzip -dc images.tar.gz | docker load
EOF
cat > "$package_root/Iniciar.sh" <<'EOF'
#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"
./Carregar-Imagens.sh
exec docker compose -f compose.yaml up -d --no-build
EOF
chmod +x "$package_root/Carregar-Imagens.sh" "$package_root/Iniciar.sh"
cat > "$package_root/Carregar-Imagens.ps1" <<'EOF'
$ErrorActionPreference = 'Stop'
$archive = Join-Path $PSScriptRoot 'images.tar.gz'
$temporary = Join-Path ([IO.Path]::GetTempPath()) ("autopack-" + [guid]::NewGuid() + '.tar')
try {
  $input = [IO.File]::OpenRead($archive)
  $gzip = [IO.Compression.GzipStream]::new($input, [IO.Compression.CompressionMode]::Decompress)
  $output = [IO.File]::Create($temporary)
  try { $gzip.CopyTo($output) } finally { $output.Dispose(); $gzip.Dispose(); $input.Dispose() }
  docker load --input $temporary
  if ($LASTEXITCODE -ne 0) { throw 'docker load falhou.' }
} finally { Remove-Item -LiteralPath $temporary -Force -ErrorAction SilentlyContinue }
EOF
cat > "$package_root/Iniciar.cmd" <<'EOF'
@echo off
cd /d "%~dp0"
where docker >nul 2>nul || (echo Docker Desktop nao encontrado.& pause & exit /b 1)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0Carregar-Imagens.ps1" || (pause& exit /b 1)
docker compose -f compose.yaml up -d --no-build
if errorlevel 1 pause
EOF
cat > "$package_root/Parar.cmd" <<'EOF'
@echo off
cd /d "%~dp0"
docker compose -f compose.yaml down
if errorlevel 1 pause
EOF
cat > "$package_root/Ver-Logs.cmd" <<'EOF'
@echo off
cd /d "%~dp0"
docker compose -f compose.yaml logs -f --tail=200
EOF
(cd "$package_root" && find . -maxdepth 1 -type f ! -name SHA256SUMS.txt -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS.txt)
[[ -s "$package_root/SHA256SUMS.txt" ]] || { echo 'Falha ao gerar hashes' >&2; exit 1; }
tar -C "$output_dir" -czf "$output_dir/${safe_product}-${version}-Docker.tar.gz" docker-package
[[ -s "$output_dir/${safe_product}-${version}-Docker.tar.gz" ]] || { echo 'Pacote Docker vazio' >&2; exit 1; }
