FROM python:3.11-slim
RUN pip install zeroconf
COPY zeroconf_peer.py /app/zeroconf_peer.py
ENTRYPOINT ["python","/app/zeroconf_peer.py"]
