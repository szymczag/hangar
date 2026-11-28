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

- The request logger records an allowlist only: method, path without query string or fragment, HTTP version, status,
  response time, and the `user-agent`, `content-type`, `content-length` and `x-request-id` headers when present.
  Query strings, bodies, every other request header and all response headers are never written.
- Every entry passes through `redactFormat`, first in the format chain. It works on a copy; the logged objects are not
  modified.
  - Fields: the value under a credential key becomes `[REDACTED]` at any depth (up to 10 levels and 5000 objects per
    entry), including inside error objects such as an axios error's `config.headers`. Credential keys are the header
    names `cookie`, `set-cookie`, `authorization`, `proxy-authorization`, `x-api-key`, `x-csrftoken`, `x-csrf-token`,
    `x-xsrf-token`, `live-server-secret-key` and `x-admin-secret-key`, any key containing `cookie`, `authorization`,
    `csrf`, `xsrf`, `sessionid` or `credential`, and any key ending in `token`, `secret`, `secretkey`, `password`,
    `apikey` or `signature` (case, `-` and `_` ignored). In a flat name/value list such as `req.rawHeaders`, the item
    after a sensitive header name is redacted.
  - Binary data (`Buffer`, typed arrays, `ArrayBuffer`) is replaced by its size, e.g. `[Buffer 42 bytes]`.
  - Strings: one of the header names above followed by `:`, anywhere in a line, raw or after a JSON-escaped `\r\n`,
    loses the rest of the line, whatever cookie names it holds; `cookie=` loses the rest of the line up to `&` or a
    quote; quoted (`"key": "…"`, `'key': '…'`) and bare (`key: '…'`) pairs with a credential key lose the value, as do
    `name=value` pairs with a credential name, also when the name is percent-encoded; `Bearer`, `Basic`, `Digest` and
    `Negotiate` credentials (any case) and `Token` followed by 16 or more token characters are replaced; and URL
    userinfo (`scheme://user:password@`) is removed.
  - The splat arguments (`Symbol.for("splat")`) are redacted too, so a `format.splat()` added after it stays clean.
- `redactSensitiveData(value)` and `redactString(text)` apply the same rules outside the logger.

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
