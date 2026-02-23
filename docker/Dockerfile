# docker/Dockerfile
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Snachala zavisimosti — luchshe dlya kesha
COPY requirements.txt /app/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -U pip wheel && \
    if [ -f requirements.txt ]; then \
        pip install -r requirements.txt; \
    else \
        pip install flask gunicorn requests pyyaml; \
    fi

# Kod prilozheniya
COPY . /app

# Port prilozheniya (sovmestim s FLASK/serve_no_reload)
ENV PORT=8000 FLASK_APP=app.py
EXPOSE 8000

# Po umolchaniyu — prodovyy zapusk cherez gunicorn (esli est),
# inache — zapasnoy prostoy server.
CMD ["/bin/sh", "-lc", "\
  if python -c 'import importlib; importlib.import_module(\"gunicorn\")' 2>/dev/null; then \
      exec gunicorn --bind 0.0.0.0:${PORT} --workers 2 --timeout 120 app:app; \
  elif [ -f serve_no_reload.py ]; then \
      exec python serve_no_reload.py; \
  else \
      exec python - <<'PY'\n\
from os import getenv\n\
from flask import Flask\n\
app = Flask(__name__)\n\
@app.get('/')\n\
def ok():\n\
    return {'ok': True, 'msg': 'Ester container is up'}\n\
app.run(host='0.0.0.0', port=int(getenv('PORT','8000')))\n\
PY\
"]
