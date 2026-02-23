#!/usr/bin/env bash
set -euo pipefail

if command -v k6 >/dev/null 2>&1; then
  echo "[k6-install] Uzhe ustanovlen: $(k6 version || true)"
  exit 0
fi

OS="$(uname -s)"
case "$OS" in
  Linux)
    if command -v apt-get >/dev/null 2>&1; then
      echo "[k6-install] Ubuntu/Debian — dobavlyaem repozitoriy Grafana"
      sudo apt-get update -y
      sudo apt-get install -y ca-certificates gnupg
      curl -fsSL https://dl.k6.io/key.gpg | sudo gpg --yes --dearmor -o /usr/share/keyrings/k6-archive-keyring.gpg
      echo "deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main" | sudo tee /etc/apt/sources.list.d/k6.list >/dev/null
      sudo apt-get update -y
      sudo apt-get install -y k6
      ;;
    elif command -v pacman >/dev/null 2>&1; then
      echo "[k6-install] Arch Linux — pacman"
      sudo pacman -Syu --noconfirm k6
      ;;
    else
      echo "[k6-install] Neizvestnyy Linux — stavim cherez Docker (grafana/k6)."
      echo "Ispolzuy docker run grafana/k6 ... ili ustanovi vruchnuyu s https://k6.io"
      exit 1
    fi
    ;;
  Darwin)
    if command -v brew >/dev/null 2>&1; then
      brew update
      brew install k6
    else
      echo "[k6-install] Ustanovi Homebrew: https://brew.sh/"
      exit 1
    fi
    ;;
  *)
    echo "[k6-install] Nepodderzhivaemaya platforma: $OS"
    exit 1
    ;;
esac

echo "[k6-install] Gotovo: $(k6 version || true)"
