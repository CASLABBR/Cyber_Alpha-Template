[CmdletBinding()]
param(
  [Parameter(Mandatory)][string]$SourceDirectory,
  [Parameter(Mandatory)][string]$OutputDirectory,
  [Parameter(Mandatory)][string]$Product,
  [Parameter(Mandatory)][string]$Version,
  [Parameter(Mandatory)][string]$Executable,
  [string]$Manufacturer = 'CASLABBR'
)

$ErrorActionPreference = 'Stop'

function Escape-Xml([string]$Value) { [Security.SecurityElement]::Escape($Value) }
function Stable-Id([string]$Prefix, [string]$Value) {
  $sha = [Security.Cryptography.SHA256]::Create()
  try { $hash = $sha.ComputeHash([Text.Encoding]::UTF8.GetBytes($Value)) }
  finally { $sha.Dispose() }
  $hex = ([BitConverter]::ToString($hash).Replace('-', '')).Substring(0, 20)
  return "$Prefix$hex"
}
function Stable-Guid([string]$Value) {
  $md5 = [Security.Cryptography.MD5]::Create()
  try { $bytes = $md5.ComputeHash([Text.Encoding]::UTF8.GetBytes("autopack-msi:$Value")) }
  finally { $md5.Dispose() }
  return ([Guid]::new($bytes)).ToString().ToUpperInvariant()
}

$source = (Resolve-Path -LiteralPath $SourceDirectory).Path
$output = [IO.Path]::GetFullPath($OutputDirectory)
$safeProduct = ($Product -replace '[^A-Za-z0-9._-]', '-').Trim('-')
if (-not $safeProduct) { throw 'Nome de produto invalido.' }
if ($Version -notmatch '^\d+\.\d+\.\d+(\.\d+)?$') { throw 'Versao MSI invalida.' }
$parts = $Version.Split('.')
$msiVersion = "$([int]$parts[0]).$([int]$parts[1]).$([int]$parts[2])"
$executableRelative = $Executable.Replace('\', '/').TrimStart('/')
if (-not $executableRelative -or $executableRelative.Split('/') -contains '..') { throw 'Executavel MSI invalido.' }
$executablePath = Join-Path $source ($executableRelative.Replace('/', [IO.Path]::DirectorySeparatorChar))
if (-not (Test-Path -LiteralPath $executablePath -PathType Leaf)) { throw "Executavel MSI inexistente: $Executable" }

$wix = Get-Command wix -ErrorAction SilentlyContinue
if (-not $wix) { throw 'WiX CLI nao encontrado. O job deve instalar a ferramenta wix antes de criar o MSI.' }
New-Item -ItemType Directory -Force -Path $output | Out-Null

$componentRefs = [Collections.Generic.List[string]]::new()
$lines = [Collections.Generic.List[string]]::new()
$lines.Add('<?xml version="1.0" encoding="utf-8"?>')
$lines.Add('<Wix xmlns="http://wixtoolset.org/schemas/v4/wxs">')
$lines.Add("  <Package Name=`"$(Escape-Xml $safeProduct)`" Manufacturer=`"$(Escape-Xml $Manufacturer)`" Version=`"$msiVersion`" UpgradeCode=`"$(Stable-Guid $safeProduct)`" Language=`"1033`">")
$lines.Add('    <MajorUpgrade DowngradeErrorMessage="A newer version is already installed." />')
$lines.Add('    <MediaTemplate EmbedCab="yes" />')
$lines.Add('    <StandardDirectory Id="ProgramFiles6432Folder">')
$lines.Add("      <Directory Id=`"INSTALLFOLDER`" Name=`"$(Escape-Xml $safeProduct)`">")

function Add-DirectoryContent([IO.DirectoryInfo]$Directory, [string]$Indent, [string]$Relative) {
  foreach ($file in @(Get-ChildItem -LiteralPath $Directory.FullName -File -Force | Sort-Object Name)) {
    if ($file.LinkType) { throw "Links simbolicos nao sao permitidos no MSI: $($file.FullName)" }
    $fileRelative = if ($Relative) { "$Relative/$($file.Name)" } else { $file.Name }
    $componentId = Stable-Id 'cmp' $fileRelative
    $fileId = Stable-Id 'fil' $fileRelative
    $componentRefs.Add($componentId)
    $lines.Add("$Indent<Component Id=`"$componentId`" Guid=`"*`">")
    $lines.Add("$Indent  <File Id=`"$fileId`" Source=`"$(Escape-Xml $file.FullName)`" KeyPath=`"yes`" />")
    $lines.Add("$Indent</Component>")
  }
  foreach ($child in @(Get-ChildItem -LiteralPath $Directory.FullName -Directory -Force | Sort-Object Name)) {
    if ($child.LinkType) { throw "Links simbolicos nao sao permitidos no MSI: $($child.FullName)" }
    $childRelative = if ($Relative) { "$Relative/$($child.Name)" } else { $child.Name }
    $directoryId = Stable-Id 'dir' $childRelative
    $lines.Add("$Indent<Directory Id=`"$directoryId`" Name=`"$(Escape-Xml $child.Name)`">")
    Add-DirectoryContent $child "$Indent  " $childRelative
    $lines.Add("$Indent</Directory>")
  }
}

Add-DirectoryContent ([IO.DirectoryInfo]$source) '        ' ''
$shortcutComponent = 'cmpShortcut'
$componentRefs.Add($shortcutComponent)
$target = "[INSTALLFOLDER]$($executableRelative.Replace('/', '\'))"
$lines.Add('        <Component Id="cmpShortcut" Guid="*">')
$lines.Add("          <Shortcut Id=`"StartMenuShortcut`" Directory=`"ProgramMenuFolder`" Name=`"$(Escape-Xml $safeProduct)`" Target=`"$(Escape-Xml $target)`" WorkingDirectory=`"INSTALLFOLDER`" />")
$lines.Add("          <RegistryValue Root=`"HKCU`" Key=`"Software\\$(Escape-Xml $Manufacturer)\\$(Escape-Xml $safeProduct)`" Name=`"Installed`" Type=`"integer`" Value=`"1`" KeyPath=`"yes`" />")
$lines.Add('        </Component>')
$lines.Add('      </Directory>')
$lines.Add('    </StandardDirectory>')
$lines.Add('    <Feature Id="MainFeature" Title="Application" Level="1">')
foreach ($componentId in $componentRefs) { $lines.Add("      <ComponentRef Id=`"$componentId`" />") }
$lines.Add('    </Feature>')
$lines.Add('  </Package>')
$lines.Add('</Wix>')

$wxs = Join-Path $output "$safeProduct-$Version.wxs"
$msi = Join-Path $output "$safeProduct-$Version-Setup.msi"
$lines | Set-Content -LiteralPath $wxs -Encoding utf8
& $wix.Source build $wxs -arch x64 -o $msi
if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $msi -PathType Leaf)) { throw 'WiX nao produziu o MSI.' }
Remove-Item -LiteralPath $wxs -Force
(Get-FileHash -LiteralPath $msi -Algorithm SHA256).Hash.ToLowerInvariant() + "  $([IO.Path]::GetFileName($msi))" | Set-Content -LiteralPath "$msi.sha256" -Encoding ascii
Write-Output $msi
