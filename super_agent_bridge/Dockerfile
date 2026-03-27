ARG BUILD_FROM=ghcr.io/home-assistant/amd64-base:3.19
FROM ${BUILD_FROM}

RUN apk add --no-cache python3 py3-aiohttp

COPY run.sh /
COPY run.py /
RUN chmod a+x /run.sh

CMD ["/run.sh"]
