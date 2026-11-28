# Logger Package

This package provides a logger and a request logger utility built using [Winston](https://github.com/winstonjs/winston). It offers customizable log levels using env and supports structured logging for general application logs and HTTP requests.

## Features.

- Dynamic log level configuration using env.
- Pre-configured winston logger for general usage (`logger`).
- Request logger middleware that logs incoming request
- Credential redaction for every log entry.

## Usage

### Adding as a package

Add this package as a dependency in package.json

```typescript
dependency: {
    ...
    @plane/logger":"*",
    ...
}
```

### Importing the Logger

```typescript
import { logger, requestLogger } from "@plane/logger";
```

### Usage

### `logger`: General Logger

Use this for general application logs.

```typescript
logger.info("This is an info log");
logger.warn("This is a warning");
logger.error("This is an error");
```

### `requestLogger`: Request Logger Middleware

Use this as a middleware for incoming requests

```typescript
const app = express();
app.use(requestLogger);
```

## Credentials stay out of logs

- The request logger records an allowlist only: method, path, HTTP version, status, response time and the
  `user-agent`, `content-type` and `content-length` headers. Query strings, bodies, cookies, authorization and CSRF
  headers, and response headers are never written.
- Every entry passes through `redactFormat` before it is serialised. Values under credential keys (`cookie`,
  `authorization`, `x-api-key`, CSRF and session names, and names ending in `token`, `secret`, `password` or
  `apiKey`) become `[REDACTED]`, at any depth, including inside error objects such as an axios error's
  `config.headers`. Strings are scrubbed of raw `Cookie:` header lines, credential `name=value` pairs and bearer
  tokens. The logged objects themselves are not modified.
- `redactSensitiveData(value)` applies the same rules to a value outside the logger.

## Available Log Levels

- `error`
- `warn`
- `info` (default)
- `http`
- `verbose`
- `debug`
- `silly`

## Log file

- Log files are stored in logs folder of current working directory. Error logs are stored in files with format `error-%DATE%.log` and combined logs are stored with format `combined-%DATE%.log`.
- Log files have a 7 day rotation period defined.

## Configuration

- By default, the log level is set to `info`.
- You can specify a log level by adding a LOG_LEVEL in .env.
