# Ester LAN server check (Win10)
$ShareName = 'LAN_SHARE'
$SharePath = '<lan-share>'
$User      = 'lanuser'
$Local     = "$env:COMPUTERNAME\$User"

# Ensure folder and NTFS
New-Item -ItemType Directory -Force -Path $SharePath | Out-Null
icacls $SharePath /inheritance:e | Out-Null
icacls $SharePath /grant "${User}:(OI)(CI)M" | Out-Null

# Share (create if missing)
if (-not (Get-SmbShare -Name $ShareName -ErrorAction SilentlyContinue)) {
  New-SmbShare -Name $ShareName -Path $SharePath -CachingMode Documents | Out-Null
}
# Grant share access to local account
Grant-SmbShareAccess -Name $ShareName -AccountName $Local -AccessRight Full -Force | Out-Null

# Network profile and services
$iface = (Get-NetIPConfiguration | Where-Object { $_.IPv4DefaultGateway } | Select-Object -First 1).InterfaceAlias
if ($iface) { Set-NetConnectionProfile -InterfaceAlias $iface -NetworkCategory Private }
foreach($s in 'FDResPub','fdPHost','SSDPSRV','upnphost','LanmanServer','LanmanWorkstation') {
  Set-Service $s -StartupType Automatic -ErrorAction SilentlyContinue
  Start-Service $s -ErrorAction SilentlyContinue
}

# SMB settings and firewall (TCP/445)
Set-SmbServerConfiguration -EnableSMB2Protocol $true -EnableSMB1Protocol $false `
  -RequireSecuritySignature $false -EnableSecuritySignature $true -Force | Out-Null
New-NetFirewallRule -DisplayName 'SMB 445 In (Private)' -Direction Inbound -Protocol TCP -LocalPort 445 `
  -Action Allow -Profile Private -Program System -ErrorAction SilentlyContinue | Out-Null

# Show status
Get-SmbShare -Name $ShareName | Format-Table Name,Path
Get-SmbShareAccess -Name $ShareName
