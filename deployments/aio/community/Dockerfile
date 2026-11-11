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
RUN apk add --no-cache \
    "libstdc++" \
    "libgcc" \
    "libpq" \
    "libxslt" \
    "xmlsec" \
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

COPY --from=backend-img /code /app/backend
COPY --from=backend-img /usr/local/lib/python3.12/site-packages/ /usr/local/lib/python3.12/site-packages/
COPY --from=backend-img /usr/local/bin/ /usr/local/bin/

RUN pip install supervisor
RUN mkdir -p /etc/supervisor/conf.d

COPY start.sh /app/start.sh
COPY dist/plane.env /app/plane.env
COPY supervisor.conf /etc/supervisor/conf.d/supervisor.conf

RUN mkdir -p /app/logs/access && \
    mkdir -p /app/logs/error && \
    mkdir -p /app/data && \
    chmod +x /app/start.sh

VOLUME ["/app/data", "/app/logs"]

EXPOSE 80 443

CMD ["/app/start.sh"] 
