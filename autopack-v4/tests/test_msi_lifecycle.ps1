$ErrorActionPreference = 'Stop'
# Installation tests belong only on disposable GitHub-hosted Windows runners.
if ($env:GITHUB_ACTIONS -ne 'true' -or $env:RUNNER_ENVIRONMENT -ne 'github-hosted') {
  throw 'Run this installation test on a disposable GitHub-hosted runner.'
}
$root = Join-Path $env:RUNNER_TEMP ('autopack-msi-' + [Guid]::NewGuid().ToString('N'))
$product = 'AutoPackFixture-' + [Guid]::NewGuid().ToString('N')
$source = Join-Path $root 'source'
$output = Join-Path $env:GITHUB_WORKSPACE 'msi-test-results'
New-Item -ItemType Directory -Path "$source/assets", $output -Force | Out-Null
$installed = Join-Path $env:ProgramFiles $product
$shortcut = Join-Path ([Environment]::GetFolderPath('CommonPrograms')) "$product.lnk"
$registry = "HKCU:\Software\CASLABBR\$product"
function Assert($Condition, [string]$Message) { if (-not $Condition) { throw $Message } }
function Invoke-Msi([string]$Operation, [string]$Package, [string]$Stage) {
  $log = Join-Path $output "$Stage.log"
  $process = Start-Process msiexec.exe -ArgumentList "$Operation `"$Package`" /qn /norestart /l*v `"$log`"" -Wait -PassThru -WindowStyle Hidden
  Assert ($process.ExitCode -in @(0, 3010)) "MSI $Stage failed: $($process.ExitCode). See $log"
}
Add-Type -TypeDefinition 'public static class Fixture { public static void Main() { System.Console.WriteLine("autopack-msi-ok"); } }' -OutputAssembly "$source/app.exe" -OutputType ConsoleApplication
$script = Join-Path $PSScriptRoot '../package-msi.ps1'
$activeMsi = $null
try {
  foreach ($version in @('1.0.0', '1.1.0')) {
    Set-Content "$source/assets/version.txt" $version
    & $script -SourceDirectory $source -OutputDirectory $output -Product $product -Version $version -Executable 'app.exe' | Out-Host
    $msi = Join-Path $output "$product-$version-Setup.msi"
    Assert ((Get-Item -LiteralPath $msi).Length -gt 0) 'Empty MSI'
    $hash = (Get-FileHash -LiteralPath $msi -Algorithm SHA256).Hash.ToLowerInvariant()
    Assert ((Get-Content "$msi.sha256" -Raw).Trim() -eq "$hash  $([IO.Path]::GetFileName($msi))") 'Checksum mismatch'
    $activeMsi = $msi
    Invoke-Msi '/i' $msi "install-$version"
    Assert ((& "$installed/app.exe") -eq 'autopack-msi-ok') 'Installed executable failed'
    Assert ((Get-Content "$installed/assets/version.txt" -Raw).Trim() -eq $version) 'Installed payload version mismatch'
    Assert (Test-Path -LiteralPath $shortcut) 'Start Menu shortcut missing'
    $link = (New-Object -ComObject WScript.Shell).CreateShortcut($shortcut)
    Assert ($link.TargetPath -eq "$installed/app.exe") "Shortcut target mismatch: $($link.TargetPath); expected $installed/app.exe"
    Assert ((Get-ItemProperty -LiteralPath $registry).Installed -eq 1) 'Install registry marker missing'
  }
  Remove-Item -LiteralPath "$installed/app.exe" -Force
  Invoke-Msi '/fa' $activeMsi 'repair'
  Assert ((& "$installed/app.exe") -eq 'autopack-msi-ok') 'Repair did not restore executable'
  Invoke-Msi '/x' $activeMsi 'uninstall'
  $activeMsi = $null
  Assert (-not (Test-Path -LiteralPath "$installed/app.exe")) 'Executable left after uninstall'
  Assert (-not (Test-Path -LiteralPath "$installed/assets/version.txt")) 'Payload left after uninstall'
  Assert (-not (Test-Path -LiteralPath $shortcut)) 'Shortcut left after uninstall'
  Assert (-not (Test-Path -LiteralPath $registry)) 'Registry marker left after uninstall'
  'Real WiX MSI: install, execute, upgrade, repair and uninstall passed.' | Tee-Object -FilePath "$output/result.txt"
} finally {
  if ($activeMsi) { Invoke-Msi '/x' $activeMsi 'cleanup' }
}
