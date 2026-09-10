FROM --platform=linux/arm64 debian:trixie-slim@sha256:c94f5ddd41327aa2d4a7cfba7889056c02936182fd76a513fec6160c97181fc0

COPY debian.sources /etc/apt/sources.list.d/debian.sources

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential ca-certificates nodejs npm python3 python3-dev python3-pip python3-venv \
    && npm install --global pnpm@9.15.1 \
    && rm -rf /var/lib/apt/lists/* /root/.cache

COPY build-application /usr/local/bin/build-application
COPY make-entry-points-relocatable /usr/local/bin/make-entry-points-relocatable

ENTRYPOINT ["build-application"]
