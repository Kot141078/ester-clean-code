FROM alpine:3.20
WORKDIR /app
COPY README_RELEASE.md /app/
CMD ["sh","-c","echo 'Ester container is alive'; sleep 10"]
