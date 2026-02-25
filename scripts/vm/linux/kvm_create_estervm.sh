#!/usr/bin/env bash
# scripts/vm/linux/kvm_create_estervm.sh
# Creation of a VM for KVT/KETU (livwirth). Required: gemu-kvm, livvirt-daemon, virtual-install, virsh.
# Primer:
#   sudo bash kvm_create_estervm.sh --name EsterVM --disk /var/lib/libvirt/images/EsterVM.qcow2 --mem 6144 --vcpus 4 --iso /isos/Win11.iso

set -euo pipefail

NAME="EsterVM"
DISK="/var/lib/libvirt/images/EsterVM.qcow2"
SIZE_GB=80
MEM_MB=6144
VCPUS=4
ISO=""
OSVARIANT="auto"
NET="default"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name) NAME="$2"; shift 2;;
    --disk) DISK="$2"; shift 2;;
    --size) SIZE_GB="$2"; shift 2;;
    --mem) MEM_MB="$2"; shift 2;;
    --vcpus) VCPUS="$2"; shift 2;;
    --iso) ISO="$2"; shift 2;;
    --net) NET="$2"; shift 2;;
    *) echo "Unknown arg: $1"; exit 1;;
  esac
done

mkdir -p "$(dirname "$DISK")"
if [[ ! -f "$DISK" ]]; then
  qemu-img create -f qcow2 "$DISK" "${SIZE_GB}G"
fi

if virsh dominfo "$NAME" >/dev/null 2>&1; then
  echo "VM $NAME already exists."
else
  cmd=(virt-install --name "$NAME" --memory "$MEM_MB" --vcpus "$VCPUS" \
       --disk "path=$DISK,format=qcow2" --os-variant "$OSVARIANT" \
       --network "network=$NET" --graphics spice --video qxl --noautoconsole)
  if [[ -n "$ISO" ]]; then
    cmd+=(--cdrom "$ISO")
  else
    cmd+=(--boot hd)
  fi
  "${cmd[@]}"
fi

echo "VM $NAME ready. Use: virsh start $NAME / virsh shutdown $NAME"
