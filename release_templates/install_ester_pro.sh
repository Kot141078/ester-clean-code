#!/usr/bin/env bash
set -euo pipefail

APP_NAME="ester"
APP_DIR="${APP_DIR:-/opt/ester}"
DATA_DIR="${DATA_DIR:-/opt/ester/data}"
SECRETS_DIR="${SECRETS_DIR:-/opt/ester/secrets}"
COMPOSE_FILE="docker-compose.prod.yml"

echo "[*] Sozdayu katalogi ${APP_DIR} {data,secrets} ..."
sudo mkdir -p "${APP_DIR}" "${DATA_DIR}" "${SECRETS_DIR}"
sudo chown -R "$USER":"$USER" "${APP_DIR}" "${DATA_DIR}" "${SECRETS_DIR}"

echo "[*] Kopiruyu fayly reliza v ${APP_DIR} ..."
cp -R . "${APP_DIR}/"

cd "${APP_DIR}"

if [ ! -f "${SECRETS_DIR}/.env" ]; then
  echo "[*] Sozdayu ${SECRETS_DIR}/.env iz config/.env.example"
  cp config/.env.example "${SECRETS_DIR}/.env"
  echo "# TODO: zapolni sekrety v ${SECRETS_DIR}/.env pered startom" >&2
fi

echo "[*] Proverka Docker..."
command -v docker >/dev/null || { echo "Ustanovi Docker"; exit 1; }
command -v docker compose >/dev/null || command -v docker-compose >/dev/null || { echo "Nuzhen docker compose"; exit 1; }

echo "[*] Zapuskayu konteynery (montiruyu secrets i data)..."
if command -v docker compose >/dev/null; then
  docker compose -f "${COMPOSE_FILE}" up -d
else
  docker-compose -f "${COMPOSE_FILE}" up -d
fi

echo "[*] Gotovo. Prover: http://localhost:5000/health"
echo "ENV: ${SECRETS_DIR}/.env   DATA: ${DATA_DIR}"
