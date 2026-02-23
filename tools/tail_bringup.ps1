Param([int]$Tail=200)
$log = "data\bringup.log"
if (Test-Path $log) { Get-Content $log -Tail $Tail } else { "bringup.log not found at $log" }
