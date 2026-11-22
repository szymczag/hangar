# Self Hosting

In this guide, we will walk you through the process of setting up a self-hosted environment. Self-hosting allows you to have full control over your applications and data. It's a great way to ensure privacy, control, and customization.

We will cover two main options for setting up your self-hosted environment: using a cloud server or using your desktop. For the cloud server, we will use an AWS EC2 instance. For the desktop, we will use Docker to create a local environment.

Let's get started!

## Setting up Docker Environment

<details>
  <summary>Option 1 - Using Cloud Server</summary>
  <p>Best way to start is to create EC2 machine on AWS. It must have minimum of 2vCPU and 4GB RAM.</p>
  <p>Run the below command to install docker engine.</p>

`curl -fsSL https://get.docker.com | sh -`

</details>

---

<details>
  <summary>Option 2 - Using Desktop</summary>

#### For Mac

  <ol>
    <li> Download Docker Desktop for Mac from the <a href="https://docs.docker.com/desktop/setup/install/mac-install/" target="_blank">Docker docs</a>. </li>
    <li> Double-click the downloaded `.dmg` file and drag the Docker app icon to the Applications folder. </li>
    <li>Open Docker Desktop from the Applications folder. You might be asked to provide your system password to install additional software.</li>
  </ol>

#### For Windows:

  <ol>
    <li>Download Docker Desktop for Windows from the <a href="https://docs.docker.com/desktop/setup/install/windows-install/" target="_blank">Docker docs</a>.</li>
    <li>Run the installer and follow the instructions. You might be asked to enable Hyper-V and "Containers" Windows features.</li>
    <li>Open Docker Desktop. You might be asked to log out and log back in, or restart your machine, for changes to take effect.</li>
  </ol>

After installation, you can verify the installation by opening a terminal (Command Prompt on Windows, Terminal app on Mac) and running the command `docker --version`. This should display the installed version of Docker.

</details>

---

## Installing Hangar

Installing Hangar is a very easy and minimal step process.

### Prerequisite

- Docker installed and running
- OS with bash scripting enabled (Ubuntu, Linux AMI, macos). Windows systems need to have [gitbash](https://git-scm.com/download/win)
- User context used must have access to docker services. In most cases, use sudo su to switch as root user
- Use the terminal (or gitbash) window to run all the future steps
- **TLS, unless you are installing on localhost.** The God Mode admin console
  requires a security key, and browsers only allow that in a secure context, so
  an instance reachable over `http://` on any other host cannot sign in to the
  console at all. Set `SITE_ADDRESS` and `CERT_EMAIL` in `variables.env` for
  automatic certificates. Setting `ADMIN_WEBAUTHN_REQUIRED=0` exists to recover
  an instance nobody can sign in to; it is not a supported way to run the
  console permanently.

### Downloading Latest Release

Download the script from the newest release on the
[Releases page](https://github.com/szymczag/hangar/releases); the commands below
use `hangar-v0.3.0`. Whichever copy you run, `install` and `upgrade` look
up the release themselves and fetch that release's compose file and settings,
but never a newer copy of the script itself: see
[Upgrading Hangar Version](#upgrading-hangar-version).
They take the newest stable release, and the newest pre-release only while no
stable release has been published, so a release candidate never replaces a
stable install. GitHub's `releases/latest` links resolve only once a stable
release exists, because they skip pre-releases.

```
mkdir plane-selfhost

cd plane-selfhost
```

#### For _Docker Compose_ based setup

```
curl -fsSL -o setup.sh https://github.com/szymczag/hangar/releases/download/hangar-v0.3.0/setup.sh

chmod +x setup.sh
```

#### For _Docker Swarm_ based setup

```
curl -fsSL -o setup.sh https://github.com/szymczag/hangar/releases/download/hangar-v0.3.0/swarm.sh

chmod +x setup.sh
```

#### How `setup.sh` verifies what it downloads

`setup.sh` is the one file you download yourself, so check it before you run
it the way [Verifying release assets](../../../README.md#verifying-release-assets)
describes. From then on, `install` and `upgrade` (and `swarm.sh` deploy and
upgrade) check every file they fetch from the release before it replaces
anything in `plane-app`:

1. They download `docker-compose.yml`, `variables.env` and, for Compose,
   `migrate-object-storage.sh` from the release `hangar-vX.Y.Z` into a scratch
   directory inside `plane-app`, and print the release and URL they use.
2. They download the release's `SHA256SUMS`. If [Cosign](https://docs.sigstore.dev/cosign/system_config/installation/)
   is installed, they also download `SHA256SUMS.sigstore.json` and run
   `cosign verify-blob` with the certificate identity
   `https://github.com/szymczag/hangar/.github/workflows/build-branch.yml@refs/tags/hangar-vX.Y.Z`
   and the issuer `https://token.actions.githubusercontent.com`. The identity
   is written in the script, not read from any downloaded file.
3. They compare each downloaded file with `SHA256SUMS` (`sha256sum`, or
   `shasum -a 256` on macOS).

Only when every check passes are the files moved into `plane-app`; otherwise
the script stops with `ERROR: ...` and `Nothing in .../plane-app has been
changed`, leaving the running deployment and its files as they were.
`setup.sh upgrade` downloads and checks the new release before it stops the
services, so an upgrade whose files do not verify leaves Hangar running.

| Situation                                                  | Default                          | `HANGAR_REQUIRE_SIGNATURE=1` |
| ---------------------------------------------------------- | -------------------------------- | ---------------------------- |
| Signature and checksums verify                             | installs                         | installs                     |
| A file does not match `SHA256SUMS`, or is not listed in it | stops                            | stops                        |
| Cosign installed, and the signature fails or is missing    | stops                            | stops                        |
| Cosign is not installed                                    | checksums only, with a `WARNING` | stops                        |
| Release up to `hangar-v0.1.0` (no `SHA256SUMS`)            | installs with a `WARNING`        | stops                        |
| Newer release without `SHA256SUMS`                         | stops                            | stops                        |
| Release cannot be downloaded, `BRANCH` not set             | stops                            | stops                        |
| Release cannot be downloaded, `BRANCH` set                 | branch files, with a `WARNING`   | stops                        |
| `HANGAR_INSTALL_SOURCE_DIR` set                            | that directory's files           | stops                        |

Without Cosign, matching checksums only show that the files agree with a list
downloaded from the same place; Cosign shows that the release workflow
published that list. Install it, and set `HANGAR_REQUIRE_SIGNATURE=1` (for example `HANGAR_REQUIRE_SIGNATURE=1
./setup.sh upgrade`) to refuse anything less.

Earlier versions of the script quietly took the files from the `preview`
branch whenever the release download failed. Now a failed release download is
an error, and the branch is used only when you name it with `BRANCH=<branch>`;
those files are not verified.

#### Building the images locally

Hangar publishes images for `linux/amd64`. On another architecture, `install`
offers to build them on the host instead (it refuses under `--yes`). It clones
the source of the release being installed (the `hangar-vX.Y.Z` tag, or the
branch named in `BRANCH`), builds `myplane/hangar-<image>:local` with
`deployments/cli/community/build.yml`, and sets `CUSTOM_BUILD=true`,
`DOCKERHUB_USER=myplane` and `APP_RELEASE=local` in `plane.env`.

The release's `docker-compose.yaml` names each Hangar image by digest, so
`setup.sh` leaves that verified file as it is and writes
`plane-app/docker-compose.override.yaml`, which points every Hangar service at
the local image with `pull_policy: never`. `setup.sh start`, `stop`,
`restart`, `logs` and `backup` pass both files to Compose; so does a plain
`docker compose` run inside `plane-app`, which loads the override by name. An
install or upgrade that pulls the published images removes the override.

---

### Proceed with setup

Above steps will set you ready to install and start plane services.

Lets get started by running the `./setup.sh` command.

This will prompt you with the below options.

#### Docker Compose

```bash
Select an Action you want to perform:
   1) Install
   2) Start
   3) Stop
   4) Restart
   5) Upgrade
   6) View Logs
   7) Backup Data
   8) Migrate Object Storage (MinIO -> SeaweedFS)
   9) Exit

Action [2]: 1
```

For the 1st time setup, type "1" as action input.

This will create a folder `plane-app` and will download 2 files inside that

- `docker-compose.yaml`
- `plane.env`

The script exits when the install is done. Review `plane-app/plane.env` (see below), then start the services.

The script also accepts the action as an argument, so you can skip the menu: `./setup.sh install|start|stop|restart|upgrade|logs|backup|migrate-storage`.

#### Docker Swarm

```bash
Select an Action you want to perform:
   1) Deploy Stack
   2) Remove Stack
   3) View Stack Status
   4) Redeploy Stack
   5) Upgrade
   6) View Logs
   7) Exit

Action [3]: 1
```

Run `docker swarm init` on the manager node first if the node is not part of a swarm yet.

For the 1st time setup, type "1" as action input. The script asks for a stack name (default `plane`), creates a folder `plane-app`, downloads 2 files inside that

- `docker-compose.yml`
- `plane.env`

and deploys the stack with `docker stack deploy` right away. Review `plane-app/plane.env` and use `Redeploy Stack` to apply changes.

---

### Continue with setup - Environment Settings

Before proceeding, we suggest you review the `plane-app/plane.env` file and set the values.
Below are the most import keys you must refer to. _<span style="color: #fcba03">You can use any text editor to edit this file</span>_.

> **Secrets are generated for you.** The template ships `SECRET_KEY`,
> `LIVE_SERVER_SECRET_KEY`, `POSTGRES_PASSWORD` and `RABBITMQ_PASSWORD` empty, and
> `setup.sh` writes random values into `plane.env` on install (with the
> object-storage pair, see [Upgrading](#upgrading-hangar-version)). The API and Live refuse
> to start while `SECRET_KEY` or `LIVE_SERVER_SECRET_KEY` is empty or a value a
> template once shipped, and exit with status 64 saying which.
>
> **Only the owner can read `plane.env` and its copies.** `setup.sh` (Compose and
> Swarm) writes `plane.env`, the `plane.env.bak` and `archive/<timestamp>.env`
> copies an upgrade keeps, and the backup archives with mode `600`, and the
> `archive/` and `backup/` folders with mode `700`, whatever the umask. Releases up
> to and including hangar-v0.2.2 (and the candidate hangar-v0.3.0-rc.1) left those files at the umask's mode, often
> `664` or `644`, so any local user could read every secret in them. The first run
> of a newer `setup.sh`, whatever the action, removes group and other access from
> `plane.env`, `plane.env.bak`, `archive/*.env`, `archive/` and `backup/`, and prints
> one `NOTICE: restricted to the owner, ...` line naming what it changed. Run
> `setup.sh` and `restore.sh` as the user that owns `plane-app/`, or as root. If
> those files were readable on a shared host, treat the secrets in them as exposed
> and rotate them ([Rotating the database and RabbitMQ passwords](#rotating-the-database-and-rabbitmq-passwords)).
>
> `DATABASE_URL` and `AMQP_URL` stay empty: the API connects with the `POSTGRES_*`
> and `RABBITMQ_*` settings, which are what the bundled database and broker were
> created with. Set a URL only for an external database or broker; it then wins,
> and a password inside it must be URL-encoded. Keep `RABBITMQ_PASSWORD` to letters
> and digits, because the API builds a URL from it.
>
> Postgres and RabbitMQ keep the password they were created with in their volumes,
> so editing `POSTGRES_PASSWORD` or `RABBITMQ_PASSWORD` later changes nothing but
> the API's side and locks it out. Use
> [the rotation procedure](#rotating-the-database-and-rabbitmq-passwords) instead.

> `LISTEN_HTTP_PORT` - This is default set to `80`. Make sure the port you choose to use is not preoccupied. (e.g `LISTEN_HTTP_PORT=8080`)

> `APP_DOMAIN` - This is default set to `localhost`. Set it to the domain or IP address you will use (eg. `hangar.example.com`).

> `WEB_URL` - This is default set to `http://${APP_DOMAIN}`. Change this to the FQDN you plan to use along with LISTEN_HTTP_PORT (eg. `https://plane.example.com:8080` or `http://[IP-ADDRESS]:8080`)

> `CORS_ALLOWED_ORIGINS` - This is default set to `http://${APP_DOMAIN}`. Change this to the FQDN you plan to use along with LISTEN_HTTP_PORT (eg. `https://plane.example.com:8080` or `http://[IP-ADDRESS]:8080`)

> `TODOIST_IMPORTS_ENABLED` - This defaults to `0`. Enable it only after the
> dedicated private import bucket is verified and API, `import-worker`, and Beat
> services share the same configuration. Compose starts an isolated worker that
> consumes only the `imports` queue. Defaults allow one active import per user,
> two per workspace, 50,000 workspace rows per 24 hours, and 10 MiB of active
> workspace source data; preview and execute requests also have independent user
> and workspace rates. Invalid or out-of-range importer settings stop startup.
> Beat is required for durable redispatch, lease recovery, and the five-minute
> cleanup reconciler. See
> [Importing from Todoist](../../../docs/importing-from-todoist.md#operator-controls-and-recovery).

> `ENABLE_GOOGLE_CALENDAR_CAPACITY` - This defaults to `0`. Before setting it
> to `1`, register the Google OAuth callback at
> `https://<your-hangar-host>/auth/google/calendar/callback/`, configure the
> existing Google client ID and secret settings, and set
> `CALENDAR_TOKEN_ENCRYPTION_KEYS` to a comma-separated Fernet keyring with the
> newest key first. Hangar stores encrypted refresh tokens and calendar IDs;
> event names and descriptions are never requested or persisted.
> `CALENDAR_CAPACITY_USER_RATE` and `CALENDAR_CAPACITY_WORKSPACE_RATE` default
> to `20/minute` and `60/minute`; requests are also capped at 25 trainers and
> 14 days. Admission fails closed if Valkey is unavailable.

> HTTPS - The bundled proxy can issue certificates. Set `SITE_ADDRESS` to your domain (default `:80`, plain HTTP), `CERT_EMAIL` for the ACME account, optionally `CERT_ACME_DNS` for a DNS challenge, and keep `LISTEN_HTTPS_PORT` (default `443`) free.

> External services - To use your own Postgres, Redis, RabbitMQ or S3 instead of the bundled containers, set `DATABASE_URL`, `REDIS_URL`, `AMQP_URL`, and `USE_MINIO=0` with the `AWS_*` values in `plane.env`.

There are many other settings you can play with. We suggest you also set up email (SMTP) so you can invite your teammates onto the platform. SMTP is not set in `plane.env`: configure it in the instance admin at `/god-mode` → Email after you start the services.

#### Client IP and rate limiting behind proxies

Some endpoints are rate-limited per client IP. Two settings in `plane.env` control how that IP is determined:

- **Hangar directly on the internet behind the bundled proxy:** set `TRUSTED_PROXIES=private_ranges` (or your load balancer's ranges) and `NUM_PROXIES=1`.
- **Behind an additional load balancer or CDN:** add its ranges to `TRUSTED_PROXIES` (space-separated, e.g. `TRUSTED_PROXIES=private_ranges 203.0.113.0/24`) and raise `NUM_PROXIES` by one per extra hop (e.g. `NUM_PROXIES=2`).
- **Leaving `NUM_PROXIES` empty and `TRUSTED_PROXIES` at its default (`0.0.0.0/0`)** keeps the current behaviour.

`AUTHENTICATION_RATE_LIMIT` (default `10/minute`) is the per-IP limit for the
anonymous sign-in, sign-up and magic-link endpoints, in DRF format
`<count>/<second|minute|hour|day>`. `API_KEY_RATE_LIMIT` (default `60/minute`)
limits requests made with an API key.

Restart the services after changing these values.

#### API worker processes

`GUNICORN_WORKERS` (default `1`) sets how many Gunicorn worker processes each
`api` container runs. Each worker holds its own memory and database connections,
so raise it with the host's CPU and RAM. Before Hangar 0.1.3 the Compose file
fixed it at `1` and `AUTHENTICATION_RATE_LIMIT` was not passed to the API, so
changing either in `plane.env` had no effect; both now apply after a restart.
Docker Swarm deploys the same file and reads the same values.

---

### Continue with setup - Start Server (Docker Compose)

Lets again run the `./setup.sh` command. You will again be prompted with the below options. This time select `2` to start the services

```bash
Select a Action you want to perform:
   1) Install
   2) Start
   3) Stop
   4) Restart
   5) Upgrade
   6) View Logs
   7) Backup Data
   8) Migrate Object Storage (MinIO -> SeaweedFS)
   9) Exit

Action [2]: 2
```

Expect something like this.  
![Downloading docker images](images/download.png)

Be patient as it might take sometime based on download speed and system configuration. If all goes well, you must see something like this

![Downloading completed](images/started.png)

This is the confirmation that all images were downloaded and the services are up & running.

You have successfully self hosted `Hangar` instance. Access the application by going to IP or domain you have configured it (e.g `https://plane.example.com:8080` or `http://[IP-ADDRESS]:8080`)

---

### Stopping the Server / Remove Stack

In case you want to make changes to `plane.env` variables, we suggest you to stop the services before doing that.

#### Docker Compose

Lets again run the `./setup.sh` command. You will again be prompted with the below options. This time select `3` to stop the services

```bash
Select a Action you want to perform:
   1) Install
   2) Start
   3) Stop
   4) Restart
   5) Upgrade
   6) View Logs
   7) Backup Data
   8) Migrate Object Storage (MinIO -> SeaweedFS)
   9) Exit

Action [2]: 3
```

If all goes well, you must see something like this

![Stop Services](images/stopped.png)

#### Docker Swarm

Lets again run the `./setup.sh` command. You will again be prompted with the below options. This time select `2` to stop the services

```bash
Select an Action you want to perform:
   1) Deploy Stack
   2) Remove Stack
   3) View Stack Status
   4) Redeploy Stack
   5) Upgrade
   6) View Logs
   7) Exit

Action [3]: 2
```

If all goes well, you will see the confirmation from docker cli

---

### Restarting the Server / Redeploy Stack

In case you want to make changes to `plane.env` variables, without stopping the server or you noticed some abnormalies in services, you can restart the services with `RESTART` / `REDEPLOY` option.

Lets again run the `./setup.sh` command. You will again be prompted with the below options. This time select `4` to restart the services

#### Docker Compose

```bash
Select a Action you want to perform:
   1) Install
   2) Start
   3) Stop
   4) Restart
   5) Upgrade
   6) View Logs
   7) Backup Data
   8) Migrate Object Storage (MinIO -> SeaweedFS)
   9) Exit

Action [2]: 4
```

If all goes well, you must see something like this

![Restart Services](images/restart.png)

#### Docker Swarm

```bash
   1) Deploy Stack
   2) Remove Stack
   3) View Stack Status
   4) Redeploy Stack
   5) Upgrade
   6) View Logs
   7) Exit

Action [3]: 4
```

If all goes well, you will see the confirmation from docker cli

---

### Upgrading Hangar Version

It is always advised to keep Hangar up to date with the latest release.

> **Back up first.** Run [Backup Data](#backup-data-docker-compose) and copy
> `plane-app/plane.env` next to the backup before every upgrade. The upgrade runs
> the new release's database migrations when it starts, and **putting the previous
> images back does not undo them**: the previous release may refuse to start on the
> migrated database, or run on a schema it does not know. To go back, restore that
> backup with its `plane.env` (see [Restore Data](#restore-data-docker-compose)) and
> start the previous release. Anything written after the backup is lost.
>
> Each stable release is tested on this path before it is published: the previous
> stable release is installed from its release assets, filled with data, backed up,
> upgraded with the new `setup.sh --yes upgrade`, and the backup is restored into a
> fresh install; the data, the uploaded files, password sign-in and API keys are
> checked after both steps.
>
> **Download the new release's `setup.sh` first.** The upgrade runs your local
> copy of the script, and the script does not update itself: `upgrade` fetches
> the new release's `docker-compose.yml`, `variables.env` and
> `migrate-object-storage.sh` (`swarm.sh`: `docker-compose.yml` and
> `variables.env`), but never a new `setup.sh`, `swarm.sh` or `restore.sh`, and it
> does not restart itself with one. Whatever the new script changes in the
> installer itself only takes effect once you run it. In particular, an upgrade
> to hangar-v0.3.0 or later run with the hangar-v0.2.2 script, or an older one,
> installs the new images but leaves `plane.env` and `plane.env.bak` at the
> umask's mode, readable by other local users. Upgrade in three steps:
>
> 1. Replace `setup.sh` with the new release's script (see
>    [Downloading Latest Release](#downloading-latest-release); for Swarm, its
>    `swarm.sh` saved as `setup.sh`) and verify it.
> 2. Run `./setup.sh upgrade`.
> 3. Check that `stat -c '%a' plane-app/plane.env` (`stat -f '%Lp'` on macOS)
>    prints `600`. A script from hangar-v0.3.0 or later prints
>    `NOTICE: restricted to the owner, ...` on its first run, whatever the action,
>    when it tightens anything, and nothing once everything is owner-only. If you
>    already upgraded with an older script, download the new one and run any
>    action with it, for example `./setup.sh start` (Swarm: `./setup.sh status`).
>
> **Object-storage credentials.** The bundled object storage takes its login from `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `plane.env`, and the proxy serves its S3 API on the application's origin. Older templates shipped the public pair `access-key` / `secret-key`, which let anybody sign requests that list, read, overwrite or delete uploads. `setup.sh` now generates a random pair on install, and on upgrade replaces any pair whose secret is still `secret-key`; it prints a notice when it does. The API and the object storage pick the new pair up together when the services start, and uploads stay where they are. The old pair is kept as `LEGACY_MINIO_ROOT_USER` / `LEGACY_MINIO_ROOT_PASSWORD` for `migrate-object-storage.sh`, which still needs it to read a volume written by MinIO. A pair you set yourself, or external S3 storage (`USE_MINIO=0` or another `AWS_S3_ENDPOINT_URL`), is left alone; with `USE_MINIO=0` the bundled storage stays idle and is not routed (see [External S3](#object-storage-minio-to-seaweedfs)). If anything outside Hangar used the old pair, give it the new one.
>
> If the API logs `SECURITY: AWS_SECRET_ACCESS_KEY is the placeholder` (for example after an upgrade run with an older `setup.sh`), replace the pair by hand: stop the services, set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `plane.env` to random values (`LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 40`), set `LEGACY_MINIO_ROOT_USER=access-key` and `LEGACY_MINIO_ROOT_PASSWORD=secret-key` if uploads still wait for `migrate-storage`, and start the services again.

> **Secrets and passwords.** Earlier templates shipped `SECRET_KEY` and
> `LIVE_SERVER_SECRET_KEY` as `change-this-key-on-deployment`, and `plane` as the
> database and RabbitMQ password. On upgrade, `setup.sh`:
>
> - replaces `SECRET_KEY` and `LIVE_SERVER_SECRET_KEY` when they are empty or a
>   template value, and prints a `NOTICE`. **Everybody is signed out once** and
>   signs in again, and pending password-reset links stop working. Settings
>   saved in God Mode (SMTP password, sign-in provider secrets) were encrypted with
>   the old key; the API re-encrypts them with the new one on its first start and
>   logs `... re-encrypted with the current SECRET_KEY.` for each. Workspace and
>   project invitation links keep working: their tokens are stored and compared
>   as they are, not verified with the key. Keys you set yourself are kept.
> - **refuses**, before it stops or changes anything, when the key would be
>   replaced and `ENABLE_GOOGLE_CALENDAR_CAPACITY=1`; see
>   [below](#replacing-a-template-secret_key-with-google-calendar-capacity).
> - **keeps** `POSTGRES_PASSWORD=plane` and `RABBITMQ_PASSWORD=plane` on a deployment
>   whose volumes already exist, and prints a `WARNING`: the database and broker
>   were created with that password, and changing it in `plane.env` alone would
>   lock the API out. Rotate them with
>   [the procedure below](#rotating-the-database-and-rabbitmq-passwords) when it
>   suits you. A password is generated only for a deployment that has no volume
>   yet.
> - pins `DATABASE_URL` or `AMQP_URL` to the old `plane:plane` URL, with a
>   `WARNING`, in one case only: the previous `docker-compose.yaml` connected with
>   that fixed URL and ignored `POSTGRES_*` / `RABBITMQ_*`, so a deployment that
>   edited those after its first start kept working on the old login. Pinning the
>   URL keeps it working; rotate the password with the procedure below and then
>   empty the URL.
>
> The API and Live now refuse to start with an empty or template `SECRET_KEY` or
> `LIVE_SERVER_SECRET_KEY`. If you upgrade the images without running
> `setup.sh upgrade`, set both to random values yourself (`openssl rand -hex 32`).
>
> **Hardening.** Every service runs with `no-new-privileges`; the application
> containers and the bundled object storage drop all Linux capabilities, and the
> proxy keeps only `NET_BIND_SERVICE`. Postgres, Valkey, RabbitMQ and the API
> report their health in `docker compose ps`, and the API and workers wait for
> healthy data services before starting. If you added your own services or
> mounts to `docker-compose.yaml`, check they still start under these settings.
>
> Docker Swarm ignores `depends_on` and its schema rejects the form used for the
> health ordering, so `swarm.sh` deploys a copy without those blocks,
> `plane-app/docker-stack.yml`, written on every deploy.
>
> **Unattended upgrades.** Pass `--yes` (`./setup.sh --yes upgrade`) or set
> `HANGAR_ASSUME_YES=1` to skip the confirmation prompt and keep the screen. An
> unattended run refuses, rather than starts, a local image build. Set
> `HANGAR_RELEASE=vX.Y.Z` to install or upgrade to that release rather than the
> latest one the GitHub API reports; `swarm.sh` reads `HANGAR_RELEASE` too.
> Add `HANGAR_REQUIRE_SIGNATURE=1` (and install Cosign) so an unattended upgrade
> refuses files it cannot verify; see
> [How `setup.sh` verifies what it downloads](#how-setupsh-verifies-what-it-downloads).

Lets again run the `./setup.sh` command. You will again be prompted with the below options. This time select `5` to upgrade the release.

#### Docker Compose

```bash
Select a Action you want to perform:
   1) Install
   2) Start
   3) Stop
   4) Restart
   5) Upgrade
   6) View Logs
   7) Backup Data
   8) Migrate Object Storage (MinIO -> SeaweedFS)
   9) Exit

Action [2]: 5
```

By choosing this, it will stop the services and then will download the latest `docker-compose.yaml` and `plane.env`.

You must expect the below message

![Alt text](images/upgrade.png)

The script exits when the upgrade is done.

> It is very important for you to validate the `plane.env` for the new changes.

Once done with making changes in `plane.env` file, jump on to `Start Server`

#### Docker Swarm

Lets again run the `./setup.sh` command. You will again be prompted with the below options. This time select `5` to upgrade the release.

```bash
   1) Deploy Stack
   2) Remove Stack
   3) View Stack Status
   4) Redeploy Stack
   5) Upgrade
   6) View Logs
   7) Exit

Action [3]: 5
```

By choosing this, it asks for confirmation, downloads the latest `docker-compose.yml` and `plane.env` (your previous `plane.env` is kept as `plane.env.bak`), and redeploys the stack automatically.

> It is very important for you to validate the `plane.env` for the new changes. If you change it, run `Redeploy Stack` again.

#### Replacing a template SECRET_KEY with Google Calendar capacity

Google Calendar capacity derives two kinds of stored identifier from
`SECRET_KEY`:

- the hashes of each trainer's selected calendars;
- the key that ties a training imported from Google (with
  `ENABLE_GOOGLE_TRAINING_MATERIALIZATION=1`) to its occurrence and to the session
  it was linked to. It comes from the Google event itself, so it cannot be
  recomputed without reading every event again.

The invitations Hangar writes into trainers' calendars are not affected: each
keeps the Google event ID stored when it was planned.

So when `SECRET_KEY` is a template value and `ENABLE_GOOGLE_CALENDAR_CAPACITY=1`,
`setup.sh upgrade` and `swarm.sh` stop with an `ERROR` before they stop or
change anything. To go ahead, run the upgrade with
`HANGAR_ROTATE_SECRET_KEY=1 ./setup.sh upgrade`, and expect:

- each trainer's calendar selection to show nothing selected until the trainer
  selects the calendars again and saves;
- trainings already imported from Google to be recognised as new occurrences on
  the next sweep, so their links to sessions have to be made again. The next full
  sweep marks the old occurrences as disappeared, and they are deleted after
  `GOOGLE_TRAINING_RETIRED_RETENTION_DAYS`.

#### Rotating the database and RabbitMQ passwords

Postgres and RabbitMQ store their password in their volumes, so the password is
changed inside each service first and in `plane.env` second. Run this from the
folder that holds `plane-app/` with the services running; the users below are
`POSTGRES_USER` and `RABBITMQ_USER` from `plane.env` (`plane` by default).

```bash
cd plane-app
compose() { docker compose -f docker-compose.yaml --env-file plane.env "$@"; }

# 1. New random passwords (letters and digits only).
NEW_DB_PASSWORD=$(LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 32)
NEW_MQ_PASSWORD=$(LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 32)

# 2. Change them inside Postgres and RabbitMQ.
# psql over the local socket, which needs no password; the container's PGHOST
# would otherwise send it over TCP, which does. The statement goes in on stdin
# (printf is a shell builtin), so the password is on no command line.
printf "ALTER ROLE plane WITH PASSWORD '%s';\n" "$NEW_DB_PASSWORD" \
  | compose exec -T plane-db psql -h /var/run/postgresql -U plane -d plane
compose exec plane-mq rabbitmqctl change_password plane "$NEW_MQ_PASSWORD"

# 3. Write them to plane.env. If the upgrade pinned DATABASE_URL or AMQP_URL to
#    the old plane:plane URL, empty it in the same edit.
sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$NEW_DB_PASSWORD/; s/^RABBITMQ_PASSWORD=.*/RABBITMQ_PASSWORD=$NEW_MQ_PASSWORD/" plane.env
cd ..

# 4. Restart, so every container connects with the new passwords.
./setup.sh restart
```

On macOS use `sed -i ''`. Between steps 2 and 4 the running containers keep
their open connections; new connections fail until the restart, so do it in one
go. For Docker Swarm, run step 2 with `docker exec` in the `plane-db` and
`plane-mq` containers on the node that runs them
(`docker ps -q -f name=<stack>_plane-db`), then redeploy the stack after step 3.

---

### View Logs

There would a time when you might want to check what is happening inside the API, Worker or any other container.

Lets again run the `./setup.sh` command. You will again be prompted with the below options.

This time select `6` to view logs.

#### Docker Compose

```bash
Select a Action you want to perform:
   1) Install
   2) Start
   3) Stop
   4) Restart
   5) Upgrade
   6) View Logs
   7) Backup Data
   8) Migrate Object Storage (MinIO -> SeaweedFS)
   9) Exit

Action [2]: 6
```

#### Docker Swarm

```bash
   1) Deploy Stack
   2) Remove Stack
   3) View Stack Status
   4) Redeploy Stack
   5) Upgrade
   6) View Logs
   7) Exit

Action [3]: 6
```

#### Service Menu Options for Logs

This will further open sub-menu with list of services

```bash
Select a Service you want to view the logs for:
   1) Web
   2) Space
   3) API
   4) Worker
   5) Beat-Worker
   6) Migrator
   7) Proxy
   8) Redis
   9) Postgres
   10) Object Storage
   11) RabbitMQ
   0) Back to Main Menu

Service: 3
```

The `admin` and `live` services have no menu entry; view them with `docker compose -f plane-app/docker-compose.yaml logs -f admin` (or `live`), or with `docker service logs <stack>_admin` on Docker Swarm.

Select any of the service to view the logs e.g. `3`. Expect something similar to this

```bash
api-1  | Waiting for database...
api-1  | Database available!
api-1  | Waiting for database migrations to complete...
api-1  | Waiting for database migrations to complete...
api-1  | Waiting for database migrations to complete...
api-1  | Waiting for database migrations to complete...
api-1  | Waiting for database migrations to complete...
api-1  | Waiting for database migrations to complete...
api-1  | Waiting for database migrations to complete...
api-1  | No migrations Pending. Starting processes ...
api-1  | Instance registered
api-1  | ENABLE_SIGNUP loaded with value from environment variable.
api-1  | ENABLE_EMAIL_PASSWORD loaded with value from environment variable.
api-1  | ENABLE_MAGIC_LINK_LOGIN loaded with value from environment variable.
api-1  | GOOGLE_CLIENT_ID loaded with value from environment variable.
api-1  | GITHUB_CLIENT_ID loaded with value from environment variable.
api-1  | GITHUB_CLIENT_SECRET loaded with value from environment variable.
api-1  | EMAIL_HOST loaded with value from environment variable.
api-1  | EMAIL_HOST_USER loaded with value from environment variable.
api-1  | EMAIL_HOST_PASSWORD loaded with value from environment variable.
api-1  | EMAIL_PORT loaded with value from environment variable.
api-1  | EMAIL_FROM loaded with value from environment variable.
api-1  | EMAIL_USE_TLS loaded with value from environment variable.
api-1  | EMAIL_USE_SSL loaded with value from environment variable.
api-1  | OPENAI_API_KEY loaded with value from environment variable.
api-1  | GPT_ENGINE loaded with value from environment variable.
api-1  | UNSPLASH_ACCESS_KEY loaded with value from environment variable.
api-1  | Checking bucket...
api-1  | Bucket 'uploads' does not exist. Creating bucket...
api-1  | Bucket 'uploads' created successfully.
api-1  | Public read access policy set for bucket 'uploads'.
api-1  | Cache Cleared
api-1  | [2024-05-02 03:56:01 +0000] [1] [INFO] Starting gunicorn 21.2.0
api-1  | [2024-05-02 03:56:01 +0000] [1] [INFO] Listening at: http://0.0.0.0:8000 (1)
api-1  | [2024-05-02 03:56:01 +0000] [1] [INFO] Using worker: uvicorn.workers.UvicornWorker
api-1  | [2024-05-02 03:56:01 +0000] [25] [INFO] Booting worker with pid: 25
api-1  | [2024-05-02 03:56:03 +0000] [25] [INFO] Started server process [25]
api-1  | [2024-05-02 03:56:03 +0000] [25] [INFO] Waiting for application startup.
api-1  | [2024-05-02 03:56:03 +0000] [25] [INFO] ASGI 'lifespan' protocol appears unsupported.
api-1  | [2024-05-02 03:56:03 +0000] [25] [INFO] Application startup complete.

```

To exit this, use `CTRL+C` and then you will land on to the main-menu with the list of actions.

Similarly, you can view the logs of other services.

---

### Backup Data (Docker Compose)

There would a time when you might want to backup your data from docker volumes to external storage like S3 or drives.

The services must be **running**: the backup copies data out of the running `plane-db`, `plane-minio`, `plane-mq` and `plane-redis` containers.

Lets again run the `./setup.sh` command. You will again be prompted with the below options. This time select `7` to Backup the data.

```bash
Select a Action you want to perform:
   1) Install
   2) Start
   3) Stop
   4) Restart
   5) Upgrade
   6) View Logs
   7) Backup Data
   8) Migrate Object Storage (MinIO -> SeaweedFS)
   9) Exit

Action [2]: 7
```

In response, you can find the backup folder

```bash
Backing up plane-db data...
Copying plane-db data directory...
Successfully backed up pgdata data
Backing up plane-minio data...
Copying plane-minio data directory...
Successfully backed up object-storage data
Backing up plane-mq data...
Copying plane-mq data directory...
Successfully backed up rabbitmq_data data
Backing up plane-redis data...
Copying plane-redis data directory...
Successfully backed up redisdata data

Backup completed successfully. Backup files are stored in /....../plane-app/backup/20240502-1120
```

Unattended: `./setup.sh backup`.

> **Keep `plane.env` with the backup.** Copy `plane-app/plane.env` into the backup
> folder with `install -m 600 plane-app/plane.env plane-app/backup/<folder>/plane.env`
> (a plain `cp` gives the copy the umask's mode) and store them together, protected
> like a password. The backup folder is mode `700` and each archive `600`: the archives hold
> data written with its database and RabbitMQ passwords, its object-storage key
> pair, and its `SECRET_KEY`, which encrypts settings saved in God Mode. A new
> install generates new values, which cannot open the restored data.
>
> The backup copies the data directories of the running services. Take it when
> nobody is using the instance, so no write lands half-way through the copy.

---

### Restore Data (Docker Compose)

When you want to restore the previously backed-up data, follow the instructions below.

1. Make sure that Hangar-CE is installed, started, and then stopped. This ensures that the Docker volumes are created. The restore script needs `jq` installed to check that Hangar is stopped.
   Put the `plane.env` saved with the backup back in `plane-app/` before you start it again: the restored
   data only opens with the passwords and keys it was written with.

1. Download the restore script using the command below. We suggest downloading it in the same folder as `setup.sh`.

   ```bash
   curl -fsSL -o restore.sh https://github.com/szymczag/hangar/releases/download/hangar-v0.3.0/restore.sh
   chmod +x restore.sh
   ```

1. Execute the command below to restore your data.

   ```bash
   ./restore.sh <path to backup folder containing *.tar.gz files>
   ```

   As an example, for a backup folder `/opt/plane-selfhost/plane-app/backup/20240722-0914`, expect the response below:

   ```bash
   --------------------------------------------
    ____  _                          /////////
   |  _ \| | __ _ _ __   ___         /////////
   | |_) | |/ _` | '_ \ / _ \   /////    /////
   |  __/| | (_| | | | |  __/   /////    /////
   |_|   |_|\__,_|_| |_|\___|        ////
                                    ////
   --------------------------------------------
   Project management tool from the future
   --------------------------------------------
   Found /opt/plane-selfhost/plane-app/backup/20240722-0914/pgdata.tar.gz
   .....Restoring plane-app_pgdata
   .....Successfully restored volume plane-app_pgdata from pgdata.tar.gz

   Found /opt/plane-selfhost/plane-app/backup/20240722-0914/redisdata.tar.gz
   .....Restoring plane-app_redisdata
   .....Successfully restored volume plane-app_redisdata from redisdata.tar.gz

   Found /opt/plane-selfhost/plane-app/backup/20240722-0914/object-storage.tar.gz
   .....Restoring plane-app_object-storage
   .....Successfully restored volume plane-app_object-storage from object-storage.tar.gz


   Restore completed successfully.
   ```

1. Start the Hangar instance using `./setup.sh start`.

   `restore.sh` exits with an error, and does not report success, when any volume
   fails to restore; do not start Hangar on that data. The archives hold files
   owned by whoever took the backup, so `restore.sh` gives the object-storage
   volume to `1000:1000`, the user SeaweedFS runs as; the database, Valkey and
   RabbitMQ take their files back themselves when they start.

   A backup taken before the move to SeaweedFS contains `uploads.tar.gz` (MinIO
   format). It restores into `plane-app_uploads`; run
   `./setup.sh migrate-storage` afterwards to copy it into SeaweedFS (see
   [Object storage: MinIO to SeaweedFS](#object-storage-minio-to-seaweedfs)).

**Restoring on a new host.** `setup.sh` generates new database and RabbitMQ
passwords for a deployment that has no volumes yet, so restore the volumes
before the installer runs, in this order:

```bash
mkdir -p plane-app
install -m 600 /path/to/backup/plane.env plane-app/plane.env
for volume in pgdata redisdata object-storage rabbitmq_data; do
  docker volume create "plane-app_${volume}"
done
./restore.sh /path/to/backup
./setup.sh --yes install   # keeps the passwords of the restored volumes
./setup.sh --yes start
```

The install takes the release named by `APP_RELEASE` in the restored
`plane.env`, the one the backup was taken on, which is what rolling back an
upgrade needs. To restore onto a newer release instead, run the install with
`HANGAR_RELEASE=vX.Y.Z`; its migrations then run on the restored data as they do
on an upgrade. The qualification restores onto the new release this way.

---

### Object storage: MinIO to SeaweedFS

The bundled S3-compatible storage (`plane-minio`) now runs
[SeaweedFS](https://github.com/seaweedfs/seaweedfs) instead of MinIO. MinIO no
longer publishes community images: the pinned image can no longer be pulled
anonymously, so new installs could not start their storage at all.

The service keeps its name and port (`plane-minio:9000`), so `plane.env`, the
proxy and external S3 settings are unchanged. Uploads now live in the
`plane-app_object-storage` volume. SeaweedFS cannot read MinIO's on-disk
format, so an existing install has to copy its uploads across **once**.

**What happens on upgrade.** `./setup.sh upgrade` stops the stack, downloads
the release and, when it finds the old `plane-app_uploads` volume, runs
`migrate-object-storage.sh`. The script:

1. starts a temporary MinIO-compatible reader on the old volume (the MinIO
   image already cached on the host, or the `pgsty/silo` MinIO fork when it is
   not) and a temporary SeaweedFS on the new volume;
2. copies every bucket with rclone and then compares every object's content;
3. marks the new volume as migrated only when every bucket verified.

The old volume is never modified or deleted. Until the migration has
finished, `./setup.sh start` refuses to start rather than serve an empty
object store.

**Running it yourself.** With the stack stopped:

```bash
./setup.sh migrate-storage
# or directly, e.g. for a non-default project name or Podman:
CONTAINER_CLI=podman ./plane-app/migrate-object-storage.sh \
  --project plane-app --env-file ./plane-app/plane.env
```

`--check` only reports (exit code `0` = nothing pending, `3` = migration
pending). Re-running after a successful migration is a no-op.

**Rolling back.** Restore the archived compose file from
`plane-app/archive/` and start the stack; it uses `plane-app_uploads`
again. Uploads made after the migration exist only in
`plane-app_object-storage`.

**Removing the old data.** Once uploads work in the upgraded install:

```bash
docker volume rm plane-app_uploads
```

**External S3.** If `plane-minio` is disabled because the install uses
external S3 storage, nothing needs migrating; set
`SKIP_OBJECT_STORAGE_MIGRATION=1` if an unused `plane-app_uploads` volume is
still present.

With `USE_MINIO=0` the `plane-minio` service stays idle: it logs that external
storage is in use, starts no storage, opens no port and reports healthy, and the
proxy no longer routes `/<bucket>` to it. Earlier releases ran it anyway, on the
`access-key` / `secret-key` template pair when the `AWS_*` values were empty,
and served it on the application's origin. Removing the service from the compose
file is no longer necessary. Set `USE_MINIO=1` again to use the bundled storage.

**Docker Swarm.** Volumes are node-local. `swarm.sh upgrade` removes the
stack and stops when the node still holds `<stack>_uploads`; run
`migrate-object-storage.sh --project <stack> --env-file <plane.env>` on that
node, then deploy the stack again.

---

<details>
   <summary><h2>Upgrading from v0.13.2 to v0.14.x</h2></summary>

This is one time activity for users who are upgrading from v0.13.2 to v0.14.0

As there has been significant changes to Self Hosting process, this step mainly covers the data migration from current (v0.13.2) docker volumes from newly created volumes

> Before we begin with migration, make sure your v0.14.0 was started and then stopped. This is required to know the newly created docker volume names.

Begin with downloading the migration script using below command

```

curl -fsSL -o migrate.sh https://raw.githubusercontent.com/makeplane/plane/master/deployments/cli/community/migration-0.13-0.14.sh

chmod +x migrate.sh

```

Now run the `./migrate.sh` command and expect the instructions as below

```
******************************************************************

This script is solely for the migration purpose only.
This is a 1 time migration of volume data from v0.13.2 => v0.14.x

Assumption:
1. Postgres data volume name ends with _pgdata
2. Minio data volume name ends with _uploads
3. Redis data volume name ends with _redisdata

Any changes to this script can break the migration.

Before you proceed, make sure you run the below command
to know the docker volumes

docker volume ls -q | grep -i "_pgdata"
docker volume ls -q | grep -i "_uploads"
docker volume ls -q | grep -i "_redisdata"

*******************************************************

Given below list of REDIS volumes, identify the prefix of source and destination volumes leaving "_redisdata"
---------------------
plane-app_redisdata
v0132_redisdata

Provide the Source Volume Prefix :
```

**Open another terminal window**, and run the mentioned 3 command. This may be different for users who have changed the volume names in their previous setup (v0.13.2)

For every command you must see 2 records something like shown in above example of `redisdata`

To move forward, you would need PREFIX of old setup and new setup. As per above example, `v0132` is the prefix of v0.13.2 and `plane-app` is the prefix of v0.14.0 setup

**Back to original terminal window**, _Provide the Source Volume Prefix_ and hit ENTER.

Now you will be prompted to _Provide Destination Volume Prefix_. Provide the value and hit ENTER

```
Provide the Source Volume Prefix : v0132
Provide the Destination Volume Prefix : plane-app
```

In case the suffixes are wrong or the mentioned volumes are not found, you will receive the error shown below. The image below displays an error for source volumes.

![Migrate Error](images/migrate-error.png)

In case of successful migration, it will be a silent exit without error.

Now its time to restart v0.14.0 setup.

</details>
