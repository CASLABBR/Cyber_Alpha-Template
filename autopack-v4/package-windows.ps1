[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$SourceDirectory,
  [Parameter(Mandatory)][string]$OutputDirectory,
  [Parameter(Mandatory)][string]$Product,
  [Parameter(Mandatory)][string]$Version,
  [ValidateSet('auto','cli','gui','web')][string]$ApplicationType = 'auto',
  [string]$Executable = ''
)

$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath $SourceDirectory).Path
$output = [IO.Path]::GetFullPath($OutputDirectory)
if (-not $Executable) {
  $candidate = Get-ChildItem -LiteralPath $source -Filter *.exe -File -Recurse |
    Where-Object Name -notmatch '^(unins|setup|install)' | Select-Object -First 1
  if (-not $candidate) { throw 'Nenhum executavel foi encontrado para empacotar.' }
  $Executable = $candidate.FullName
} elseif (-not [IO.Path]::IsPathRooted($Executable)) {
  $Executable = Join-Path $source $Executable
}
if (-not (Test-Path -LiteralPath $Executable -PathType Leaf)) { throw "Executavel inexistente: $Executable" }

$safeProduct = ($Product -replace '[^A-Za-z0-9._-]', '-').Trim('-')
if (-not $safeProduct) { $safeProduct = 'AutoPack-Application' }
$portable = Join-Path $output "$safeProduct-$Version-Portable"
New-Item -ItemType Directory -Force -Path $portable | Out-Null
Get-ChildItem -LiteralPath $source -Force | Copy-Item -Destination $portable -Recurse -Force
$exeName = Split-Path -Leaf $Executable

if ($ApplicationType -eq 'auto') {
  $ApplicationType = if ((Get-ChildItem $source -Filter '*.dll' -File | Where-Object Name -match 'PresentationFramework|WindowsForms').Count) { 'gui' } else { 'cli' }
}
if ($ApplicationType -eq 'cli') {
  @"
@echo off
setlocal
cd /d "%~dp0"
"%~dp0$exeName" %*
set "AUTOPACK_EXIT=%ERRORLEVEL%"
if not "%AUTOPACK_EXIT%"=="0" pause
exit /b %AUTOPACK_EXIT%
"@ | Set-Content -LiteralPath (Join-Path $portable 'Executar.cmd') -Encoding ascii
  @"
@echo off
cd /d "%~dp0"
cmd /k ""%~dp0$exeName" --help"
"@ | Set-Content -LiteralPath (Join-Path $portable 'Abrir-Terminal.cmd') -Encoding ascii
} elseif ($ApplicationType -eq 'web') {
  @"
@echo off
cd /d "%~dp0"
start "AutoPack Server" "$exeName"
timeout /t 2 /nobreak >nul
start "" http://localhost:8000/
"@ | Set-Content -LiteralPath (Join-Path $portable 'Iniciar.cmd') -Encoding ascii
}

@"
$safeProduct $Version

Edicao portatil: extraia toda a pasta antes de executar.
Aplicacao detectada: $ApplicationType
Executavel: $exeName
"@ | Set-Content -LiteralPath (Join-Path $portable 'LEIA-ME.txt') -Encoding utf8

$manifest = [ordered]@{
  schema = 'https://caslabbr.github.io/autopack/artifact/v3'
  product = $safeProduct; version = $Version; type = $ApplicationType
  executable = $exeName; created_at = [DateTime]::UtcNow.ToString('o')
  architecture = $env:PROCESSOR_ARCHITECTURE
}
$manifest | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $portable 'build-manifest.json') -Encoding utf8
$hashes = Get-ChildItem -LiteralPath $portable -File -Recurse | Sort-Object FullName | ForEach-Object {
  $relative = [IO.Path]::GetRelativePath($portable, $_.FullName).Replace('\','/')
  "{0}  {1}" -f (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant(), $relative
}
$hashes | Set-Content -LiteralPath (Join-Path $portable 'SHA256SUMS.txt') -Encoding ascii
$zip = Join-Path $output "$safeProduct-$Version-Windows-Portable.zip"
Compress-Archive -Path (Join-Path $portable '*') -DestinationPath $zip -Force
Write-Output $zip
