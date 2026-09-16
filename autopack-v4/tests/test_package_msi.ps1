$ErrorActionPreference = 'Stop'
$root = Join-Path $PSScriptRoot ('msi-fixture-' + [Guid]::NewGuid().ToString('N'))
$oldPath = $env:PATH
function Assert($Condition, [string]$Message) {
  if (-not $Condition) { throw $Message }
}
try {
  $source = New-Item -ItemType Directory -Path "$root/source/assets" -Force
  New-Item -ItemType Directory -Path "$root/bin" -Force | Out-Null
  Set-Content "$root/source/app.exe" 'fixture executable'
  Set-Content "$root/source/assets/a & b.txt" 'fixture data'
  @'
param($Command, $Wxs, $arch, $o)
if ($Command -ne 'build' -or $arch -ne 'x64') { throw 'Unexpected WiX arguments' }
Copy-Item -LiteralPath $Wxs -Destination "$o.xml"
[IO.File]::WriteAllText($o, 'fixture MSI; not an installable package')
$global:LASTEXITCODE = 0
'@ | Set-Content "$root/bin/wix.ps1"
  $env:PATH = "$root/bin$([IO.Path]::PathSeparator)$oldPath"
  $script = Join-Path $PSScriptRoot '../package-msi.ps1'
  $params = @{ SourceDirectory = "$root/source"; OutputDirectory = "$root/output"; Product = 'Fixture'; Version = '1.2.3.4'; Executable = 'app.exe'; Manufacturer = 'A & B' }
  $msi = & $script @params
  Assert (Test-Path -LiteralPath $msi) 'MSI missing'
  [xml]$xml = Get-Content -LiteralPath "$msi.xml" -Raw
  Assert ($xml.Wix.Package.Version -eq '1.2.3') 'MSI version was not normalized'
  Assert ($xml.Wix.Package.Manufacturer -eq 'A & B') 'XML escaping failed'
  $files = @($xml.SelectNodes('//*[local-name()="File"]'))
  Assert ($files.Count -eq 2) 'Nested payload file missing'
  $expected = 'fil' + ([BitConverter]::ToString([Security.Cryptography.SHA256]::Create().ComputeHash([Text.Encoding]::UTF8.GetBytes('app.exe'))).Replace('-', '')).Substring(0, 20)
  Assert (@($files | Where-Object Id -eq $expected).Count -eq 1) 'Stable file ID changed'
  $hash = (Get-FileHash -LiteralPath $msi -Algorithm SHA256).Hash.ToLowerInvariant()
  Assert ((Get-Content -LiteralPath "$msi.sha256" -Raw).Trim() -eq "$hash  $([IO.Path]::GetFileName($msi))") 'Invalid checksum sidecar'
  $first = $xml.OuterXml
  & $script @params | Out-Null
  [xml]$again = Get-Content -LiteralPath "$msi.xml" -Raw
  Assert ($first -eq $again.OuterXml) 'WiX definition is not deterministic'
  foreach ($invalid in @(@{ Executable = '../escape.exe' }, @{ Executable = 'missing.exe' }, @{ Version = 'invalid' })) {
    $bad = $params.Clone()
    foreach ($key in $invalid.Keys) { $bad[$key] = $invalid[$key] }
    $failed = $false
    try { & $script @bad | Out-Null } catch { $failed = $true }
    Assert $failed 'Invalid input unexpectedly succeeded'
  }
  Write-Output "MSI regression tests passed on PowerShell $($PSVersionTable.PSVersion) (WiX stub)."
} finally {
  $env:PATH = $oldPath
  if (Test-Path -LiteralPath $root) { Remove-Item -LiteralPath $root -Recurse -Force }
}
