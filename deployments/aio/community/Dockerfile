ARG PLANE_VERSION=v0.27.1
ARG IMAGE_PREFIX=ghcr.io/szymczag/hangar-
FROM --platform=$BUILDPLATFORM docker.io/tonistiigi/binfmt AS binfmt

# **************************************************
#  STAGE 0: Image Loading
# **************************************************
FROM docker.io/library/node:22-alpine AS node

FROM ${IMAGE_PREFIX}web:${PLANE_VERSION} AS web-img
FROM ${IMAGE_PREFIX}api:${PLANE_VERSION} AS backend-img
FROM ${IMAGE_PREFIX}space:${PLANE_VERSION} AS space-img
FROM ${IMAGE_PREFIX}admin:${PLANE_VERSION} AS admin-img
FROM ${IMAGE_PREFIX}live:${PLANE_VERSION} AS live-img
FROM ${IMAGE_PREFIX}proxy:${PLANE_VERSION} AS proxy-img

# **************************************************
#  STAGE 1: Runner
# **************************************************
FROM docker.io/library/python:3.12.12-alpine AS runner

WORKDIR /app

# grpcio (pulled in by the OTLP gRPC exporter) ships its own roots.pem, which
# still trusts emSign ECC Root CA - G3 (eMudhra incident); point it at the system
# bundle, which the OS update below keeps current.
ENV GRPC_DEFAULT_SSL_ROOTS_FILE_PATH=/etc/ssl/certs/ca-certificates.crt

# OS security updates. --available forces reinstall from the current repos;
# bump APK_SECURITY_PATCH to bust buildx's cached layer (keyed on this command
# string), otherwise a rebuild silently re-ships the old packages. Release
# builds pass a per-run value, so every release refreshes this layer.
ARG APK_SECURITY_PATCH=2026-11-11
RUN echo "apk-security-patch ${APK_SECURITY_PATCH}" && apk update && apk upgrade --no-cache --available

# The node binary only links libstdc++ and libgcc_s from /usr/lib, so install
# them from apk instead of copying node:22-alpine's whole /usr/lib. That copy
# overwrote the libraries upgraded above (libcrypto, libssl, libz, libapk) with
# node's copies from a different Alpine release, shipping unpatched versions
# and breaking /sbin/apk.
#
# The backend's site-packages are copied from the api image below, so every
# runtime package apps/api/Dockerfile.api installs is needed here too:
# libmagic (python-magic loads it to validate uploads, and it ships the magic
# database) and gnupg (the mailer runs gpg for OpenPGP email). A test keeps the
# two lists in step.
RUN apk add --no-cache \
    "libstdc++" \
    "libgcc" \
    "libpq" \
    "libmagic" \
    "libxslt" \
    "xmlsec" \
    "gnupg" \
    "ca-certificates" \
    "openssl" \
    "nss-tools" \
    "bash" \
    "curl" \
    "uuidgen" \
    "ncdu" \
    "vim"

COPY --from=node /usr/local/lib /usr/local/lib
COPY --from=node /usr/local/include /usr/local/include
COPY --from=node /usr/local/bin /usr/local/bin

# Runtime services execute node and workspace binaries directly; the package
# manager and its dependency tree are not needed in the final AIO image.
RUN rm -rf /usr/local/lib/node_modules/npm /usr/local/bin/npm /usr/local/bin/npx

COPY --from=web-img /usr/share/nginx/html /app/web
COPY --from=space-img /app /app/space
COPY --from=admin-img /usr/share/nginx/html/god-mode /app/admin
COPY --from=live-img /app /app/live

RUN rm -rf /app/space/apps/space/.next/cache

COPY --from=proxy-img /usr/bin/caddy /usr/bin/caddy
COPY dist/Caddyfile /app/proxy/Caddyfile

# Security headers for web and God Mode: each image's header template, which
# @plane/csp generated from that build (inline-script hashes included), and the
# start-up hook that gives its variables their values. start.sh renders them
# into the Caddy snippets the Caddyfile imports.
COPY --from=web-img /etc/nginx/templates/security-headers.conf.template /app/proxy/security-headers/web.conf.template
COPY --from=admin-img /etc/nginx/templates/security-headers.conf.template /app/proxy/security-headers/admin.conf.template
COPY --from=web-img /docker-entrypoint.d/15-hangar-csp.envsh /app/proxy/security-headers/15-hangar-csp.envsh
COPY render-security-headers.py /app/proxy/render-security-headers.py

COPY --from=backend-img /code /app/backend
COPY --from=backend-img /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=backend-img /usr/local/bin/ /usr/local/bin/

RUN pip install supervisor

# pip is only needed for the install above. The runner base's own pip vendors a
# certifi that still trusts the compromised emSign G3 root (GHSA-6q48-6c7w-9gw2),
# so drop it before the image ships.
RUN rm -rf /usr/local/lib/python3.12/site-packages/pip \
           /usr/local/lib/python3.12/site-packages/pip-*.dist-info \
           /usr/local/bin/pip /usr/local/bin/pip3 /usr/local/bin/pip3.12
RUN mkdir -p /etc/supervisor/conf.d

COPY start.sh /app/start.sh
COPY dist/plane.env /app/plane.env
COPY supervisor.conf /etc/supervisor/conf.d/supervisor.conf
# supervisorctl looks for /etc/supervisord.conf, not the conf.d path above.
RUN ln -s /etc/supervisor/conf.d/supervisor.conf /etc/supervisord.conf

RUN mkdir -p /app/logs/access && \
    mkdir -p /app/logs/error && \
    mkdir -p /app/data && \
    chmod +x /app/start.sh

VOLUME ["/app/data", "/app/logs"]

EXPOSE 80 443

CMD ["/app/start.sh"] 
