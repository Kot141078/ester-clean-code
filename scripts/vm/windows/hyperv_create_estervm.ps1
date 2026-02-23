# scripts\vm\windows\hyperv_create_estervm.ps1
<#
Sozdanie VM Hyper-V dlya Ester.
Primer:
  .\hyperv_create_estervm.ps1 -VmName EsterVM -Vhd D:\VMs\EsterVM.vhdx -MemGB 6 -Switch EsterSwitch -Iso D:\ISO\Win11.iso
Trebovaniya: Windows 10/11 Pro, rol Hyper-V vklyuchena (Enable-WindowsOptionalFeature Microsoft-Hyper-V -All)
#>

param(
  [Parameter(Mandatory=$true)][string]$VmName,
  [Parameter(Mandatory=$true)][string]$Vhd,
  [int]$MemGB = 6,
  [string]$Switch = "EsterSwitch",
  [string]$Iso = ""
)

$ErrorActionPreference = "Stop"

if (-not (Get-Command New-VM -ErrorAction SilentlyContinue)) {
  throw "Hyper-V ne ustanovlen. Vklyuchite komponent Microsoft-Hyper-V."
}

if (-not (Get-VMSwitch -Name $Switch -ErrorAction SilentlyContinue)) {
  Write-Host "==> Sozdayu vnutrenniy svitch $Switch"
  New-VMSwitch -Name $Switch -SwitchType Internal | Out-Null
}

if (-not (Test-Path $Vhd)) {
  $dir = Split-Path $Vhd
  New-Item -ItemType Directory -Force -Path $dir | Out-Null
  Write-Host "==> Sozdayu VHDX $Vhd (dinamicheskiy 80GB)"
  New-VHD -Path $Vhd -SizeBytes 80GB -Dynamic | Out-Null
}

if (Get-VM -Name $VmName -ErrorAction SilentlyContinue) {
  Write-Host "==> VM $VmName uzhe suschestvuet — propuskayu sozdanie."
} else {
  Write-Host "==> Sozdayu VM $VmName"
  New-VM -Name $VmName -MemoryStartupBytes ($MemGB * 1GB) -Generation 2 -SwitchName $Switch | Out-Null
  Add-VMHardDiskDrive -VMName $VmName -Path $Vhd
  Set-VM -Name $VmName -AutomaticStartAction StartIfRunning -AutomaticStopAction Save
  # Videokonsol — po umolchaniyu
}

if ($Iso -and (Test-Path $Iso)) {
  if (-not (Get-VMDvdDrive -VMName $VmName -ErrorAction SilentlyContinue)) {
    Add-VMDvdDrive -VMName $VmName -Path $Iso | Out-Null
  } else {
    Set-VMDvdDrive -VMName $VmName -Path $Iso | Out-Null
  }
}

Write-Host "==> VM $VmName gotova. Ustanovka OS cherez ISO pri pervom starte: Start-VM -Name $VmName"
