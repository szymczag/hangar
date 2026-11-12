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
    <li> Download Docker Desktop for Mac from the <a href="https://hub.docker.com/editions/community/docker-ce-desktop-mac/" target="_blank">Docker Hub</a>. </li>
    <li> Double-click the downloaded `.dmg` file and drag the Docker app icon to the Applications folder. </li>
    <li>Open Docker Desktop from the Applications folder. You might be asked to provide your system password to install additional software.</li>
  </ol>

#### For Windows:

  <ol>
    <li>Download Docker Desktop for Windows from the <a href="https://hub.docker.com/editions/community/docker-ce-desktop-windows/" target="_blank">Docker Hub</a>.</li>
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

Hangar publishes every release as a GitHub pre-release, so GitHub's
`releases/latest` links do not resolve. Download the script from the newest
release on the [Releases page](https://github.com/szymczag/hangar/releases); the
commands below use `hangar-v0.1.0-rc.71`. Whichever copy you run, `install` and
`upgrade` look up the newest published release themselves, pre-releases
included, and fetch that release's compose file and settings.

```
mkdir plane-selfhost

cd plane-selfhost
```

#### For _Docker Compose_ based setup

```
curl -fsSL -o setup.sh https://github.com/szymczag/hangar/releases/download/hangar-v0.1.0-rc.71/setup.sh

chmod +x setup.sh
```

#### For _Docker Swarm_ based setup

```
curl -fsSL -o setup.sh https://github.com/szymczag/hangar/releases/download/hangar-v0.1.0-rc.71/swarm.sh

chmod +x setup.sh
```

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

Again the `options [1-9]` will be popped up, and this time hit `9` to exit.

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

For the 1st time setup, type "1" as action input.

This will create a create a folder `plane-app` and will download 2 files inside that

- `docker-compose.yaml`
- `plane.env`

Again the `options [1-7]` will be popped up, and this time hit `7` to exit.

---

### Continue with setup - Environment Settings

Before proceeding, we suggest used to review `.env` file and set the values.
Below are the most import keys you must refer to. _<span style="color: #fcba03">You can use any text editor to edit this file</span>_.

> `LISTEN_HTTP_PORT` - This is default set to `80`. Make sure the port you choose to use is not preoccupied. (e.g `LISTEN_HTTP_PORT=8080`)

> `WEB_URL` - This is default set to `http://localhost`. Change this to the FQDN you plan to use along with LISTEN_HTTP_PORT (eg. `https://plane.example.com:8080` or `http://[IP-ADDRESS]:8080`)

> `CORS_ALLOWED_ORIGINS` - This is default set to `http://localhost`. Change this to the FQDN you plan to use along with LISTEN_HTTP_PORT (eg. `https://plane.example.com:8080` or `http://[IP-ADDRESS]:8080`)

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

There are many other settings you can play with, but we suggest you configure `EMAIL SETTINGS` as it will enable you to invite your teammates onto the platform.

#### Client IP and rate limiting behind proxies

Some endpoints are rate-limited per client IP. Two settings in `plane.env` control how that IP is determined:

- **Hangar directly on the internet behind the bundled proxy:** set `TRUSTED_PROXIES=private_ranges` (or your load balancer's ranges) and `NUM_PROXIES=1`.
- **Behind an additional load balancer or CDN:** add its ranges to `TRUSTED_PROXIES` (space-separated, e.g. `TRUSTED_PROXIES=private_ranges 203.0.113.0/24`) and raise `NUM_PROXIES` by one per extra hop (e.g. `NUM_PROXIES=2`).
- **Leaving `NUM_PROXIES` empty and `TRUSTED_PROXIES` at its default (`0.0.0.0/0`)** keeps the current behaviour.

Restart the services after changing these values.

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

> Download the latest `setup.sh` (see [Downloading Latest Release](#downloading-latest-release)) before upgrading: the upgrade runs your local copy of the script.
>
> **Object-storage credentials.** The bundled object storage takes its login from `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `plane.env`, and the proxy serves its S3 API on the application's origin. Older templates shipped the public pair `access-key` / `secret-key`, which let anybody sign requests that list, read, overwrite or delete uploads. `setup.sh` now generates a random pair on install, and on upgrade replaces any pair whose secret is still `secret-key`; it prints a notice when it does. The API and the object storage pick the new pair up together when the services start, and uploads stay where they are. The old pair is kept as `LEGACY_MINIO_ROOT_USER` / `LEGACY_MINIO_ROOT_PASSWORD` for `migrate-object-storage.sh`, which still needs it to read a volume written by MinIO. A pair you set yourself, or external S3 storage (`USE_MINIO=0` or another `AWS_S3_ENDPOINT_URL`), is left alone; with `USE_MINIO=0` the bundled storage stays idle and is not routed (see [External S3](#object-storage-minio-to-seaweedfs)). If anything outside Hangar used the old pair, give it the new one.
>
> If the API logs `SECURITY: AWS_SECRET_ACCESS_KEY is the placeholder` (for example after an upgrade run with an older `setup.sh`), replace the pair by hand: stop the services, set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `plane.env` to random values (`LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 40`), set `LEGACY_MINIO_ROOT_USER=access-key` and `LEGACY_MINIO_ROOT_PASSWORD=secret-key` if uploads still wait for `migrate-storage`, and start the services again.

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

Once done, choose `9` to exit from prompt.

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

By choosing this, it will stop the services and then will download the latest `docker-compose.yaml` and `plane.env`.

Once done, choose `7` to exit from prompt.

> It is very important for you to validate the `plane.env` for the new changes.

Once done with making changes in `plane.env` file, jump on to `Redeploy Stack`

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

---

### Restore Data (Docker Compose)

When you want to restore the previously backed-up data, follow the instructions below.

1. Make sure that Hangar-CE is installed, started, and then stopped. This ensures that the Docker volumes are created.

1. Download the restore script using the command below. We suggest downloading it in the same folder as `setup.sh`.

   ```bash
   curl -fsSL -o restore.sh https://github.com/szymczag/hangar/releases/download/hangar-v0.1.0-rc.71/restore.sh
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

   A backup taken before the move to SeaweedFS contains `uploads.tar.gz` (MinIO
   format). It restores into `plane-app_uploads`; run
   `./setup.sh migrate-storage` afterwards to copy it into SeaweedFS (see
   [Object storage: MinIO to SeaweedFS](#object-storage-minio-to-seaweedfs)).

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

curl -fsSL -o migrate.sh https://raw.githubusercontent.com/makeplane/plane/master/deploy/selfhost/migration-0.13-0.14.sh

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
