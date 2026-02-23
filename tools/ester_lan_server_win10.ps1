<# 
Ester / LAN Server (Win10)

Mosty:
- Yavnyy: (SMB ↔ Ester-khranilische) — odna obschaya tochka pravdy dlya ingest/snapshots.
- Skrytyy #1: (Sluzhby obnaruzheniya ↔ Provodnik) — publikatsiya uzla, chtoby ego videli bez vvoda IP.
- Skrytyy #2: (Fayrvol ↔ Doverie) — tolko nuzhnye gruppy pravil, nichego lishnego.

Zemnoy abzats (inzheneriya):
Eto «stoyka s diskom i dvumya avtomatami»: sluzhba publikatsii — chtoby stoyku nashli, fayrvol — chtoby ne dulo, prava NTFS — chtoby nikto ne vydral shnur logicheski.

# c=a+b
#>

$SharePath = 'D:\LAN_Share'       # uzhe est — ne strashno, sozdadim pri otsutstvii
$ShareName = 'LAN_SHARE'
$User      = 'lanuser'

# Papka + NTFS-prava
New-Item -ItemType Directory -Force -Path $SharePath | Out-Null
icacls $SharePath /inheritance:e | Out-Null
icacls $SharePath /grant "${User}:(OI)(CI)M" | Out-Null

# Shara (povtorno bezopasno)
if (-not (Get-SmbShare -Name $ShareName -ErrorAction SilentlyContinue)) {
  New-SmbShare -Name $ShareName -Path $SharePath -FullAccess $User -CachingMode Documents | Out-Null
} else {
  Set-SmbShare -Name $ShareName -FolderEnumerationMode AccessBased | Out-Null
}

# Sluzhby, profil seti, SMB
$if = (Get-NetIPConfiguration | ? { $_.IPv4DefaultGateway } | Select-Object -First 1).InterfaceAlias
if ($if) { Set-NetConnectionProfile -InterfaceAlias $if -NetworkCategory Private }
foreach($s in 'FDResPub','fdPHost','SSDPSRV','upnphost','LanmanServer','LanmanWorkstation'){
  Set-Service $s -StartupType Automatic -ErrorAction SilentlyContinue
  Start-Service $s -ErrorAction SilentlyContinue
}
Set-SmbServerConfiguration -EnableSMB2Protocol $true -EnableSMB1Protocol $false `
  -RequireSecuritySignature $false -EnableSecuritySignature $true -Force | Out-Null

# Faervol (RU/EN gruppy — chto naydetsya)
'Network Discovery','Obnaruzhenie seti','File and Printer Sharing','Obschiy dostup k faylam i printeram' |
  % { Get-NetFirewallRule -DisplayGroup $_ -ErrorAction SilentlyContinue | Enable-NetFirewallRule | Out-Null }

Write-Host "Gotovo (Win10). Shara: \\$env:COMPUTERNAME\$ShareName  Put: $SharePath"
