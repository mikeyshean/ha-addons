ARG BUILD_FROM=ghcr.io/hassio-addons/base:20.0.1
FROM ${BUILD_FROM}

RUN apk add --no-cache python3 py3-aiohttp

COPY rootfs /
COPY run.py /

ENTRYPOINT ["/init"]
