@echo off
wsl -e bash -lc "pkill -f serve_no_reload.py || true; pkill -f run_bot.sh || true; pkill -f telegram_bot || true"
