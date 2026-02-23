Param(
  [string]$ShareName="ester-data",
  [string]$Path="D:\ester-data"
)
Write-Host "Share check:"
try { Get-SmbShare -Name $ShareName | Format-List Name,Path,Description,FolderEnumerationMode } catch {}
Write-Host "Path ACL:"
cmd /c "icacls `"$Path`""
