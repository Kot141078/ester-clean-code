
# PowerShell helper: korrektnye one-liners dlya proverki
# Zapusk:  powershell -NoLogo -NoProfile -File tools\verify_ps.ps1
Write-Host "PYTHON: " -NoNewline; python -V

# Pravilnye odnostrochniki (NE isp. bash here-doc <<'PY'):
python -c "from modules.subconscious import engine as se; print(se.tick_once('smoke'))"
python -c "from modules.graph import dag_engine as dg; g=dg.build_graph({'A':{'fn':lambda **k: 'ok','deps':[]}}); print(g.run())"
python -c "from modules.judge import select_best, synthesize; print(select_best(['a','bbb','cc'])); print(synthesize(['a','bbb','cc']))"
