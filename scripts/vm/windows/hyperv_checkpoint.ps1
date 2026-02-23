# scripts\vm\windows\hyperv_checkpoint.ps1
<#
Snapshoty (Checkpoints) Hyper-V: sozdat/vosstanovit/spisok/udalit.
Primery:
  .\hyperv_checkpoint.ps1 -Name EsterVM -Create pre-upgrade
  .\hyperv_checkpoint.ps1 -Name EsterVM -Restore pre-upgrade
  .\hyperv_checkpoint.ps1 -Name EsterVM -List
  .\hyperv_checkpoint.ps1 -Name EsterVM -Delete broken-state
#>
param(
  [Parameter(Mandatory=$true)][string]$Name,
  [string]$Create,
  [string]$Restore,
  [switch]$List,
  [string]$Delete
)

$ErrorActionPreference = "Stop"

if ($List) {
  Get-VMSnapshot -VMName $Name | Select-Object -Property Name, CreationTime, IsDeleted, IsAutomatic
  exit 0
}
if ($Create) {
  Checkpoint-VM -Name $Name -SnapshotName $Create | Out-Null
  Write-Host "Checkpoint '$Create' sozdan."
  exit 0
}
if ($Restore) {
  Stop-VM -Name $Name -Force -TurnOff | Out-Null
  Restore-VMSnapshot -VMName $Name -Name $Restore -Confirm:$false | Out-Null
  Write-Host "Vosstanovleno k '$Restore'."
  exit 0
}
if ($Delete) {
  Remove-VMSnapshot -VMName $Name -Name $Delete -Confirm:$false
  Write-Host "Checkpoint '$Delete' udalen."
  exit 0
}

Write-Host "Nichego ne sdelano. Ispolzuyte -Create/-Restore/-List/-Delete."
