[CmdletBinding()]
param(
  [Parameter(Mandatory=$true)][string]$SrcDir,
  [Parameter(Mandatory=$true)][string]$OutFile
)
$ErrorActionPreference='Stop'
$enc = [System.Text.Encoding]::UTF8
New-Item -ItemType Directory -Force -Path ([System.IO.Path]::GetDirectoryName($OutFile)) | Out-Null
Remove-Item -Force -ErrorAction SilentlyContinue $OutFile

$files = Get-ChildItem -LiteralPath $SrcDir -File -Include *.txt,*.md -Recurse
$written = 0
foreach ($f in $files) {
  # Chitaem «syro» .NET-metodom: bez PS NoteProperty, vsegda UTF-8
  $text = [System.IO.File]::ReadAllText($f.FullName, $enc)
  $obj = [ordered]@{
    id   = $f.FullName
    text = $text
    meta = @{ fname = $f.Name; mtime=$f.LastWriteTimeUtc; size=$f.Length }
  }
  $line = ($obj | ConvertTo-Json -Depth 5 -Compress)
  [System.IO.File]::AppendAllText($OutFile, $line + "`n", $enc)
  $written++
}
"OK: wrote $written docs to $OutFile"
