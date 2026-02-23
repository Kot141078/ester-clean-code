# deploy/Dockerfile — konteyner Ester (Synergy)
# MOSTY:
# - (Yavnyy) Python 3.11 slim + uvicorn; stavim neobkhodimye biblioteki dlya FastAPI/Flask/SSE.
# - (Skrytyy #1) Nulevye privyazki k konkretnym privatnym modulyam; prosto kopiruem repozitoriy kak est.
# - (Skrytyy #2) Bezopasnye defolty: unbuffered, no bytecode, neizmenyaemyy UID.

# ZEMNOY ABZATs:
# Sobiraet edinyy obraz, kotoryy zapuskaet asgi.app_main:app — i API, i bordu. c=a+b

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Bazovye zavisimosti (minimum)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates tini && \
    rm -rf /var/lib/apt/lists/*

# Ustanavlivaem neobkhodimyy piton-zoopark (bez navyazyvaniya opentelemetrii)
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir \
      uvicorn[standard]==0.30.* \
      fastapi==0.110.* \
      starlette==0.37.* \
      flask==3.* \
      jinja2>=3.1 \
      httpx>=0.27

# Kopiruem proekt
COPY . /app

# Papka dlya dannykh (SQLite)
RUN mkdir -p /app/data && \
    adduser --disabled-password --gecos "" ester && \
    chown -R ester:ester /app
USER ester

EXPOSE 8080

ENV HOST=0.0.0.0 PORT=8080 WORKERS=2 LOG_LEVEL=info

ENTRYPOINT ["/usr/bin/tini","--"]
CMD ["python","-m","uvicorn","asgi.app_main:app","--host","0.0.0.0","--port","8080","--log-level","info","--workers","2"]
