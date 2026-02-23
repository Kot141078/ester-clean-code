
param(
    [int]$Port = 8137,
    [ValidateSet("A","B")] [string]$Mode = "A" # A=dry-run (po umolchaniyu), B=kill
)
<# 
scripts/port_free.ps1 — diagnostika/osvobozhdenie TCP-porta na Windows.

Mosty:
- Yavnyy: (DevOps ↔ Prilozhenie) osvobozhdaet i diagnostiruet zanyatyy port pered zapuskom Ester.
- Skrytyy #1: (Bezopasnost ↔ Nadezhnost) ne ubivaet protsessy po umolchaniyu (Mode=A), trebuet yavnogo Mode=B.
- Skrytyy #2: (UI/Stsenarii ↔ Infrastruktura) sovmestim s vashimi .ps1-lancherami, ne menyaet ikh signatury.

Zemnoy abzats (inzheneriya):
Kogda Win soobschaet 10048 (address already in use), eto znachit, chto port uzhe zanyat
drugim protsessom ili zavis v TIME_WAIT/finalnom sostoyanii. Etot skript pokazyvaet,
kto derzhit port, i pri Mode=B akkuratno zavershaet protsessy vladeltsev.

Anti-ekho. Bezopasnaya samo-redaktura: A/B-slot cherez -Mode (A—inertnyy), B — boevoy.
Pri oshibke avtokatbek: esli Stop-Process ne udalsya — tolko preduprezhdenie, bez padeniya.
c=a+b
#>

function Get-PortOwners {
    param([int]$Port)
    $conns = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    if (-not $conns) { return @() }
    $owners = @()
    foreach ($c in $conns) {
        try {
            $pid = $c.OwningProcess
            $proc = Get-Process -Id $pid -ErrorAction SilentlyContinue
            $owners += [PSCustomObject]@{
                PID = $pid
                Name = $proc.Name
                State = $c.State
                LocalAddress = $c.LocalAddress
                LocalPort = $c.LocalPort
                RemoteAddress = $c.RemoteAddress
                RemotePort = $c.RemotePort
            }
        } catch {
            $owners += [PSCustomObject]@{
                PID = $pid
                Name = "<unknown>"
                State = $c.State
                LocalAddress = $c.LocalAddress
                LocalPort = $c.LocalPort
                RemoteAddress = $c.RemoteAddress
                RemotePort = $c.RemotePort
            }
        }
    }
    return $owners
}

$owners = Get-PortOwners -Port $Port
if (-not $owners -or $owners.Count -eq 0) {
    Write-Host "[ok] Port $Port is free."
    exit 0
}

Write-Host "[warn] Port $Port is busy by:"
$owners | Format-Table -AutoSize

if ($Mode -eq "A") {
    Write-Host "[info] Mode=A (dry-run). No processes were terminated. Re-run with -Mode B to free the port."
    exit 0
}

foreach ($o in $owners) {
    try {
        Write-Host "[act] Stop-Process -Id $($o.PID) ($($o.Name))"
        Stop-Process -Id $o.PID -Force -ErrorAction Stop
    } catch {
        Write-Warning "Failed to stop PID $($o.PID): $($_.Exception.Message)"
    }
}

Start-Sleep -Seconds 1
$owners2 = Get-PortOwners -Port $Port
if (-not $owners2 -or $owners2.Count -eq 0) {
    Write-Host "[ok] Port $Port is free now."
    exit 0
} else {
    Write-Warning "Port $Port still busy:"
    $owners2 | Format-Table -AutoSize
    exit 1
}
