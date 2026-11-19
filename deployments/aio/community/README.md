# Hangar Community All-In-One (AIO) Docker Image

The Hangar Community All-In-One Docker image packages all Hangar services into a single container for easy deployment and testing. This image includes web interface, API server, background workers, live server, and more.

## What's Included

The AIO image contains the following services:

- **Proxy** (Port 80, 443): Caddy reverse proxy, the only exposed entry point
- **Web App**: Main Hangar web interface, served as static files by the proxy at `/`
- **Admin**: Instance admin (God mode), served as static files by the proxy at `/god-mode`
- **Space** (internal port 3002): Public project spaces at `/spaces`
- **API Server** (internal port 3004): Backend API at `/api` and `/auth`
- **Live Server** (internal port 3005): Real-time collaboration at `/live`
- **Worker & Beat**: Background task processing
- **Migrator**: Runs database migrations at startup

## Prerequisites

### Required External Services

The AIO image requires these external services to be running:

- **PostgreSQL Database**: For data storage
- **Redis**: For caching and session management
- **RabbitMQ**: For message queuing
- **S3-Compatible Storage**: For file uploads (AWS S3 or MinIO)

### Required Environment Variables

You must provide these environment variables:

#### Core Configuration

- `DOMAIN_NAME`: Your domain name or IP address, with `:port` when the instance is published on a port other than 80 or 443 (e.g. `hangar.example.com:8443`), so `WEB_URL`, redirects and allowed origins keep the port
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `AMQP_URL`: RabbitMQ connection string

#### Storage Configuration

- `AWS_REGION`: AWS region (e.g., us-east-1)
- `AWS_ACCESS_KEY_ID`: S3 access key
- `AWS_SECRET_ACCESS_KEY`: S3 secret key
- `AWS_S3_BUCKET_NAME`: S3 bucket name
- `AWS_S3_ENDPOINT_URL`: S3 endpoint (optional, defaults to `https://s3.${AWS_REGION}.amazonaws.com`)

## Quick Start

### Basic Usage

```bash
docker run --name plane-aio --rm -it \
    -p 80:80 \
    -e DOMAIN_NAME=your-domain.com \
    -e DATABASE_URL=postgresql://user:pass@host:port/database \
    -e REDIS_URL=redis://host:port \
    -e AMQP_URL=amqp://user:pass@host:port/vhost \
    -e AWS_REGION=us-east-1 \
    -e AWS_ACCESS_KEY_ID=your-access-key \
    -e AWS_SECRET_ACCESS_KEY=your-secret-key \
    -e AWS_S3_BUCKET_NAME=your-bucket \
    -v hangar-aio-data:/app/data \
    ghcr.io/szymczag/hangar-aio:v0.1.0
```

The `stable` tag follows the newest stable release and moves when the next one
is published. For a durable deployment, pin the image to a version or its
verified digest; see
[Verifying release images](../../../README.md#verifying-release-images).

### Example with IP Address

```bash
MYIP=192.168.68.169
docker run --name myaio --rm -it \
    -p 80:80 \
    -e DOMAIN_NAME=${MYIP} \
    -e DATABASE_URL=postgresql://plane:plane@${MYIP}:15432/plane \
    -e REDIS_URL=redis://${MYIP}:16379 \
    -e AMQP_URL=amqp://plane:plane@${MYIP}:15673/plane \
    -e AWS_REGION=us-east-1 \
    -e AWS_ACCESS_KEY_ID=5MV45J9NF5TEFZWYCRAX \
    -e AWS_SECRET_ACCESS_KEY=7xMqAiAHsf2UUjMH+EwICXlyJL9TO30m8leEaDsL \
    -e AWS_S3_BUCKET_NAME=plane-app \
    -e AWS_S3_ENDPOINT_URL=http://${MYIP}:19000 \
    -e FILE_SIZE_LIMIT=10485760 \
    -v hangar-aio-data:/app/data \
    ghcr.io/szymczag/hangar-aio:v0.1.0
```

## Configuration Options

### Optional Environment Variables

#### Network & Protocol

- `SITE_ADDRESS`: Server bind address (default: `:80`). Set it to your domain (e.g. `hangar.example.com`) to have Caddy serve HTTPS on 443 with an automatic certificate.
- `APP_PROTOCOL`: `http` or `https` (default: `http`). Used to build `WEB_URL` from `DOMAIN_NAME`.

#### Security & Secrets

- `SECRET_KEY`: Django secret key. It signs sessions and encrypts saved instance
  settings, so it must stay the same for the life of the deployment. Generated on
  first boot if not set.
- `LIVE_SERVER_SECRET_KEY`: Live server secret. Generated on first boot if not set.

A value passed with `-e` always wins and is not written to disk. A generated
value is kept in `/app/data/secrets.env` (mode `600`), so **mount a named volume
or a host directory at `/app/data`**, as the examples above do. The image
declares `/app/data` as a volume, but without a mount `docker run --rm` or
recreating the container gives it a new, empty anonymous volume: new keys are
generated, everybody is signed out, and saved instance settings can no longer be
decrypted. Back up `secrets.env` with the database.

Images up to Hangar 0.1.2 kept the generated keys in `/app/plane.env` inside the
container. The first start of a newer image in the same container copies them to
`/app/data/secrets.env`. If you are about to replace such a container, read its
keys first and pass them as `-e SECRET_KEY=...` and `-e LIVE_SERVER_SECRET_KEY=...`
(or write them to `secrets.env` on the new data volume):

```bash
docker exec <old-container> grep -E '^(SECRET_KEY|LIVE_SERVER_SECRET_KEY)=' /app/plane.env
```

- `REDIS_SSL_CERT_REQS`: For a `rediss://` `REDIS_URL`, the Redis server certificate and hostname are verified by default (`required`). Set it to `none` to skip verification.
- `REDIS_SSL_CA_CERTS`: Path inside the container to a CA bundle, for a Redis server whose certificate is issued by a private CA. Mount the file with `-v`, for example `-v /path/to/redis-ca.pem:/certs/redis-ca.pem:ro -e REDIS_SSL_CA_CERTS=/certs/redis-ca.pem`.

#### Content-Security-Policy and Security Headers

Web and God Mode send the same security headers as the web and admin images of
a Compose or Helm installation: the Content-Security-Policy generated from each
build (with `frame-ancestors 'none'`), the Trusted Types policy (report-only by
default), `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff` and
`Referrer-Policy: strict-origin-when-cross-origin`. The container renders them
from those images' templates when it starts and refuses to start if it cannot.
Space sends its own policy. `Strict-Transport-Security` is not sent; put the
container behind a proxy that adds it if you need it.

Uploads go straight to object storage, so the origin of
`AWS_S3_PUBLIC_ENDPOINT_URL` (else `AWS_S3_ENDPOINT_URL`), and the bucket's
virtual-hosted subdomain of it, are added to `img-src`, `connect-src` and
`media-src`. The `HANGAR_CSP_*` variables described in
[content-security-policy.md](../../../docs/content-security-policy.md#configuration)
(`HANGAR_CSP_REPORT_ONLY`, `HANGAR_CSP_TRUSTED_TYPES`, extra origins) work here
too; a value with a quote, backslash, backtick or brace stops the container.

#### File Handling

- `FILE_SIZE_LIMIT`: Maximum file upload size in bytes (default: `5242880` = 5MB)

#### API Configuration

- `API_KEY_RATE_LIMIT`: API key rate limit (default: `60/minute`)

## Port Mapping

The following ports are exposed:

- `80`: Main web interface (HTTP)
- `443`: HTTPS (only when `SITE_ADDRESS` is set to a domain)

## Volume Mounts

### Persistent Volumes

`/app/data` is required for a deployment you keep: it holds the generated
secrets (see [Security & Secrets](#security--secrets)). `/app/logs` is
recommended.

```bash
-v /path/to/logs:/app/logs \
-v /path/to/data:/app/data
```

A host directory mounted at `/app/logs` may start empty: the container creates
`access/` and `error/` in it on every start.

## Building the Image

To build the AIO image yourself:

```bash
cd deployments/aio/community
./build.sh --release=v0.1.0 --image-name=my-hangar-aio
```

`build.sh` prepares the `dist/` directory and prints the `docker build` command to
run next; it does not build the image itself.

Available build options:

- `--release`: Hangar version to build (required)
- `--image-name`: Custom image name (default: `ghcr.io/szymczag/hangar-aio`; the
  `IMAGE_NAME` environment variable sets the same value)

## Troubleshooting

### Logs

All service logs are available in `/app/logs/`:

- Access logs: `/app/logs/access/`
- Error logs: `/app/logs/error/`

### Health Checks

The container runs multiple services managed by Supervisor. Check service status:

```bash
docker exec -it <container-name> supervisorctl status
```

### Common Issues

1. **Database Connection Failed**: Ensure PostgreSQL is accessible and credentials are correct
2. **Redis Connection Failed**: Verify Redis server is running and URL is correct
3. **File Upload Issues**: Check S3 credentials and bucket permissions

### Environment Validation

The container will validate required environment variables on startup and display helpful error messages if any are missing.

### Environment variable precedence

At startup the container writes the variables above into `/app/plane.env` and then exports every line of that file. Variables that the start script does not manage (for example `CERT_EMAIL`, `CERT_ACME_CA`, `CERT_ACME_DNS`, `DEBUG`, `GUNICORN_WORKERS`, `AUTHENTICATION_RATE_LIMIT`, `MINIO_ENDPOINT_SSL`, `WEBHOOK_ALLOWED_IPS`, `WEBHOOK_ALLOWED_HOSTS`, `API_BASE_URL`) keep the value from `/app/plane.env`, even if you pass them with `-e`. To change them, mount your own copy of the file: `-v /path/to/plane.env:/app/plane.env`.

## Production Considerations

- Use proper SSL certificates for HTTPS
- Configure proper backup strategies for data
- Monitor resource usage and scale accordingly
- Use external load balancer for high availability
- Regularly update to latest versions
- Secure your environment variables and secrets

## Support

For issues and support, see the [Hangar documentation](../../../README.md) or open a [GitHub issue](https://github.com/szymczag/hangar/issues). Report security issues privately through [GitHub security advisories](https://github.com/szymczag/hangar/security/advisories/new).
