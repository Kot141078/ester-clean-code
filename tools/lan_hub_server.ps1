Param(
  [string]$ShareName = "ester-data",
  [string]$Path = "D:\ester-data",
  [switch]$GrantEveryone = $true
)
# 1) Katalog
New-Item -ItemType Directory -Force -Path $Path | Out-Null

# 2) NTFS permissions (the localized name "Everene" is obtained from the S-1-1-0 LED)
$EveryoneSid = New-Object System.Security.Principal.SecurityIdentifier 'S-1-1-0'
$Everyone = $EveryoneSid.Translate([System.Security.Principal.NTAccount]).Value
if ($GrantEveryone) {
  cmd /c "icacls `"$Path`" /grant `"$Everyone`":(OI)(CI)M /T" | Out-Null
}

# 3) SMB sluzhby
Start-Service LanmanServer -ErrorAction SilentlyContinue
Start-Service LanmanWorkstation -ErrorAction SilentlyContinue

# 4) Fayrvoll: vklyuchaem bazovye pravila SMB (po imenam pravil, oni stabilny na RU/EN)
$fwNames = @('FPS-SMB-In-TCP','FPS-NB-Name-In-UDP','FPS-NB-Session-In-TCP','FPS-NB-Datagram-In-UDP')
foreach($n in $fwNames){
  try { Get-NetFirewallRule -Name $n -ErrorAction Stop | Enable-NetFirewallRule | Out-Null } catch {}
}

# 5) Shara
$share = Get-SmbShare -Name $ShareName -ErrorAction SilentlyContinue
if (-not $share) {
  # create, gives full access to Everene (for girls)
  New-SmbShare -Name $ShareName -Path $Path -FullAccess $Everyone -ChangeAccess $Everyone -ReadAccess $Everyone | Out-Null
} else {
  # if it exists, we will update access
  try { Grant-SmbShareAccess -Name $ShareName -AccountName $Everyone -AccessRight Full -Force | Out-Null } catch {}
}

# 6) Additionally: we will give Change to authenticated users
$AuthUsers = (New-Object System.Security.Principal.SecurityIdentifier 'S-1-5-11').Translate([System.Security.Principal.NTAccount]).Value
try { Grant-SmbShareAccess -Name $ShareName -AccountName $AuthUsers -AccessRight Change -Force | Out-Null } catch {}

# 7) Vyvod
$host = try { (Get-CimInstance Win32_ComputerSystem).DNSHostName } catch { $env:COMPUTERNAME }
$unc = "\\{0}\{1}" -f $host,$ShareName
$out = @{
  ok = $true
  unc = $unc
  path = $Path
  share = $ShareName
  everyone = $Everyone
  auth_users = $AuthUsers
}
$out | ConvertTo-Json -Compress
