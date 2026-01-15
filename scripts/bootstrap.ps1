param(
  [Parameter(Mandatory=$true)]
  [string]$ProjectName,
  [string]$Domain = "domain"
)

$root = Split-Path -Parent $PSScriptRoot
$replacements = @{
  "<project_name>" = $ProjectName
  "<domain>" = $Domain
}

$files = Get-ChildItem -Path $root -Recurse -File -Include *.md,*.txt,*.py,*.java,*.gradle
foreach ($f in $files) {
  $content = Get-Content $f.FullName -Raw
  $updated = $content
  foreach ($k in $replacements.Keys) {
    $updated = $updated -replace [regex]::Escape($k), $replacements[$k]
  }
  if ($updated -ne $content) {
    Set-Content -Encoding ASCII -Path $f.FullName -Value $updated
  }
}

$logbook = Join-Path $root "docs\LOGBOOK.md"
if (Test-Path $logbook) {
  $stamp = (Get-Date).ToString("yyyy-MM-dd")
  Add-Content -Encoding ASCII -Path $logbook -Value ("- $stamp: <handle>: initialized project from template.")
}

Write-Output "Bootstrap complete. Update AGENTS.md and PERMISSIONS.md as needed."
