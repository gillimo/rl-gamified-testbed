param(
  [string]$Root = (Split-Path -Parent $PSScriptRoot)
)

$placeholders = @('<project_name>', '<domain>')
$files = Get-ChildItem -Path $Root -Recurse -File -Include *.md,*.txt,*.py,*.java,*.gradle
$found = @()
foreach ($f in $files) {
  $content = Get-Content $f.FullName -Raw
  foreach ($p in $placeholders) {
    if ($content -match [regex]::Escape($p)) {
      $found += "$($f.FullName):$p"
    }
  }
}

$rootName = Split-Path -Leaf $Root
if ($rootName -eq "new_project_template") {
  if ($found.Count -gt 0) {
    Write-Output "Template placeholders present (expected). Run after bootstrap to validate.";
    exit 0
  }
  Write-Output "Template validation passed."
  exit 0
}

if ($found.Count -gt 0) {
  Write-Output "Placeholders still present:"
  $found | ForEach-Object { Write-Output "- $_" }
  exit 1
}

Write-Output "Template validation passed."
