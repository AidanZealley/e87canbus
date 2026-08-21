FROM --platform=linux/arm64 debian:trixie-slim@sha256:c94f5ddd41327aa2d4a7cfba7889056c02936182fd76a513fec6160c97181fc0

ARG RPI_IMAGE_GEN_REVISION=262d4df5a9f9d4133370465399a7958a7c22cdc7

COPY debian.sources /etc/apt/sources.list.d/debian.sources

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && git clone https://github.com/raspberrypi/rpi-image-gen.git /opt/rpi-image-gen \
    && git -C /opt/rpi-image-gen checkout --detach "${RPI_IMAGE_GEN_REVISION}" \
    && /opt/rpi-image-gen/install_deps.sh \
    && rm -rf /var/lib/apt/lists/* /opt/rpi-image-gen/.git

WORKDIR /opt/rpi-image-gen
ENTRYPOINT ["/opt/rpi-image-gen/rpi-image-gen"]
