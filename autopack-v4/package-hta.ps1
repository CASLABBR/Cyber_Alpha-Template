[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$SourceDirectory,
  [Parameter(Mandatory)][string]$OutputDirectory,
  [Parameter(Mandatory)][string]$Product,
  [Parameter(Mandatory)][string]$Version
)
$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath $SourceDirectory).Path
if (-not (Test-Path -LiteralPath (Join-Path $source 'index.html'))) { throw 'index.html nao encontrado.' }
$safe = ($Product -replace '[^A-Za-z0-9._-]', '-').Trim('-')
if (-not $safe) { $safe = 'AutoPack-HTA' }
$root = [IO.Path]::GetFullPath($OutputDirectory)
$package = Join-Path $root "$safe-$Version-HTA"
New-Item -ItemType Directory -Force -Path $package | Out-Null
Get-ChildItem -LiteralPath $source -Force | Copy-Item -Destination $package -Recurse -Force
@"
<html><head><title>$safe</title>
<hta:application id="AutoPack" applicationname="$safe" border="thin" caption="yes" maximizebutton="yes" singleinstance="yes" />
<style>html,body,iframe{width:100%;height:100%;margin:0;border:0;overflow:hidden}</style></head>
<body><iframe application="yes" src="index.html"></iframe></body></html>
"@ | Set-Content -LiteralPath (Join-Path $package "$safe.hta") -Encoding utf8
@"
$safe $Version
Abra $safe.hta. HTA usa o motor legado do Windows; sites modernos podem exigir o pacote PWA, Tauri ou navegador.
"@ | Set-Content -LiteralPath (Join-Path $package 'LEIA-ME.txt') -Encoding utf8
$hashes = Get-ChildItem $package -File -Recurse | ForEach-Object {
  "{0}  {1}" -f (Get-FileHash $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant(), [IO.Path]::GetRelativePath($package,$_.FullName).Replace('\','/')
}
$hashes | Set-Content (Join-Path $package 'SHA256SUMS.txt') -Encoding ascii
Compress-Archive -Path (Join-Path $package '*') -DestinationPath (Join-Path $root "$safe-$Version-HTA.zip") -Force
