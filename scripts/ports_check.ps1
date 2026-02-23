Param([int[]]$Ports = @(80,443,5000,8080,8137))
Write-Host "Proveryayu zanyatye porty:" ($Ports -join ", ")
foreach ($p in $Ports) {
  try {
    $c = Get-NetTCPConnection -LocalPort $p -State Listen -ErrorAction SilentlyContinue
    if ($c) {
      $owners = ($c | ForEach-Object {
        try { (Get-Process -Id $_.OwningProcess).ProcessName } catch { "pid="+$_.OwningProcess }
      } | Sort-Object -Unique) -join ","
      Write-Host ("[BUSY] {0} => {1}" -f $p, $owners)
    } else {
      Write-Host ("[FREE] {0}" -f $p)
    }
  } catch { Write-Host ("[?] {0} (net dannykh)" -f $p) }
}
Write-Host "`nEsli zanyat 80/443 — ispolzuy PORT=8137 i HOST=127.0.0.1"
