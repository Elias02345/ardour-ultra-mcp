# syntax=docker/dockerfile:1
FROM public.ecr.aws/docker/library/debian:sid-slim
RUN --mount=type=secret,id=system_ca,required=true,mode=0444 \
    sed -i 's|http://deb.debian.org|https://deb.debian.org|g' /etc/apt/sources.list.d/debian.sources && \
    apt-get -o Acquire::https::CaInfo=/run/secrets/system_ca update && \
    apt-get -o Acquire::https::CaInfo=/run/secrets/system_ca install -y --no-install-recommends ardour ardour-lv2-plugins xvfb x11-utils python3 python3-venv ca-certificates git && \
    rm -rf /var/lib/apt/lists/*
WORKDIR /project
