Param([string]$Drive = "Z")
$Drive = $Drive.TrimEnd(':') + ":"
& cmd.exe /c "net use $Drive /delete /y"
if ($LASTEXITCODE -eq 0) { "OK: unmapped $Drive" } else { "WARN: unmap code=$LASTEXITCODE" }
