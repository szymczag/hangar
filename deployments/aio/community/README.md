# Hangar Community All-In-One (AIO) Docker Image

The Hangar Community All-In-One Docker image packages all Hangar services into a single container for easy deployment and testing. This image includes web interface, API server, background workers, live server, and more.

## What's Included

The AIO image contains the following services:

- **Web App**: Main Hangar web interface, served as static files by the proxy at `/`
- **Space** (Port 3002): Public project spaces
- **Admin**: Administrative interface, served as static files by the proxy at `/god-mode`
- **API Server** (Port 3004): Backend API
- **Live Server** (Port 3005): Real-time collaboration
- **Proxy** (Port 80, 443): Caddy reverse proxy
- **Worker & Beat**: Background task processing

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

- `DOMAIN_NAME`: Your domain name or IP address
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string
- `AMQP_URL`: RabbitMQ connection string

#### Storage Configuration

- `AWS_REGION`: AWS region (e.g., us-east-1)
- `AWS_ACCESS_KEY_ID`: S3 access key
- `AWS_SECRET_ACCESS_KEY`: S3 secret key
- `AWS_S3_BUCKET_NAME`: S3 bucket name
- `AWS_S3_ENDPOINT_URL`: S3 endpoint (optional, defaults to AWS)

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

- `SITE_ADDRESS`: Server bind address (default: `:80`)

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

#### File Handling

- `FILE_SIZE_LIMIT`: Maximum file upload size in bytes (default: `5242880` = 5MB)

#### API Configuration

- `API_KEY_RATE_LIMIT`: API key rate limit (default: `60/minute`)

## Port Mapping

The following ports are exposed:

- `80`: Main web interface (HTTP)
- `443`: HTTPS (if SSL configured)

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

## Production Considerations

- Use proper SSL certificates for HTTPS
- Configure proper backup strategies for data
- Monitor resource usage and scale accordingly
- Use external load balancer for high availability
- Regularly update to latest versions
- Secure your environment variables and secrets

## Support

For issues and support, please refer to the official Hangar documentation.
