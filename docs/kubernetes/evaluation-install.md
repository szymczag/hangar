# Install Hangar for evaluation

This tutorial installs Hangar `0.1.0-rc.35` in a dedicated namespace with bundled,
persistent PostgreSQL, Valkey, RabbitMQ, and object storage. When complete, you
will have a TLS-enabled Hangar instance suitable for evaluation and compatibility
testing.

> [!WARNING]
> This profile is single-node application infrastructure, not a highly available
> production deployment. Use a disposable or non-critical cluster and a new
> namespace. There is no supported in-place migration from `plane-ce`.

## Before you begin

You need:

- an AMD64 Kubernetes 1.30–1.36 cluster, including Kubernetes 1.36.2;
- Helm 4.2 and a compatible `kubectl`;
- an ingress controller with WebSocket support;
- a DNS name that resolves to the ingress endpoint;
- a TLS certificate and private key for that name;
- a CNI that enforces `NetworkPolicy`; and
- a default `StorageClass`, or one selected explicitly for all four bundled
  stateful services.

Set the release parameters used throughout this tutorial:

```bash
export CHART_VERSION=0.1.0-rc.35
export RELEASE_NAME=hangar
export NAMESPACE=hangar-evaluation
export HANGAR_HOST=hangar-evaluation.example.com
```

Replace `HANGAR_HOST` with your DNS name before continuing.

## 1. Confirm the chart is reachable

This command does not require GHCR credentials:

```bash
helm show chart oci://ghcr.io/szymczag/charts/hangar \
  --version "$CHART_VERSION"
```

Confirm the output reports chart version `0.1.0-rc.35`, application version
`v0.1.0-rc.35`, and the expected Kubernetes version constraint.

For higher-assurance environments, complete [artifact verification](security.md#verify-release-010-rc29)
before installation.

## 2. Create a Restricted namespace

```bash
kubectl create namespace "$NAMESPACE"
kubectl label namespace "$NAMESPACE" \
  pod-security.kubernetes.io/enforce=restricted \
  pod-security.kubernetes.io/audit=restricted \
  pod-security.kubernetes.io/warn=restricted
```

If your admission system applies additional policies, verify that it does not
weaken the Restricted baseline to admit the chart.

## 3. Create the TLS Secret

Use a certificate whose Subject Alternative Name contains `HANGAR_HOST`:

```bash
kubectl --namespace "$NAMESPACE" create secret tls hangar-tls \
  --cert=/secure/path/tls.crt \
  --key=/secure/path/tls.key
```

Do not place certificate private keys in a values file or Helm command line.

## 4. Create application and dependency Secrets

Download the release-matched Secret structure into a private local file:

```bash
umask 077
curl --fail --location --silent --show-error \
  --output evaluation-secrets.yaml \
  https://raw.githubusercontent.com/szymczag/hangar/hangar-v0.1.0-rc.35/charts/hangar/examples/evaluation-secrets.example.yaml
```

Replace every `CHANGE_ME` value with a unique, randomly generated credential.
Keep URL credentials and their corresponding dependency fields identical. URL
encode reserved characters in `DATABASE_URL`, `REDIS_URL`, and `AMQP_URL`.

The example assumes release name `hangar`. If you change `RELEASE_NAME`, update
the service names embedded in those URLs before applying the file.

Store the populated values in your secret-management system. Apply the rendered
Secret resources without printing their contents to CI logs or shell history:

```bash
kubectl --namespace "$NAMESPACE" apply --filename evaluation-secrets.yaml
```

Verify names and keys without decoding values:

```bash
kubectl --namespace "$NAMESPACE" get secret \
  hangar-application hangar-live hangar-database \
  hangar-cache hangar-queue hangar-object-storage
```

## 5. Prepare evaluation values

Create `evaluation-values.yaml` from this release-compatible example:

```yaml
deploymentProfile: evaluation

publicUrl:
  scheme: https
  host: hangar-evaluation.example.com

evaluation:
  enabled: true

ingress:
  className: nginx
  annotations:
    nginx.ingress.kubernetes.io/proxy-body-size: 6m
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
    nginx.ingress.kubernetes.io/force-ssl-redirect: "true"
  tls:
    secretName: hangar-tls

networkPolicy:
  ingressController:
    preset: nginx
```

The maintained copy is
[`charts/hangar/examples/evaluation-values.yaml`](../../charts/hangar/examples/evaluation-values.yaml).

Edit these fields:

- `publicUrl.host` to match `HANGAR_HOST`;
- `ingress.className` and annotations for your ingress controller;
- `networkPolicy.ingressController.preset` if the controller is not the
  community `ingress-nginx` controller; use `custom` with complete selectors
  when no built-in preset matches; and
- all four storage-class fields when the cluster has no suitable default class.

The example uses annotations for the community ingress-nginx controller. Other
controllers require equivalent HTTPS redirect, request-size, and WebSocket
configuration.

Direct browser uploads use a presigned same-origin path derived from the bucket
name. With the default configuration, the chart routes `/hangar` to bundled
SeaweedFS. Do not add a competing Ingress or HTTPRoute for that path.

## 6. Render and inspect the release

Render the exact public package before installing it:

```bash
helm template "$RELEASE_NAME" oci://ghcr.io/szymczag/charts/hangar \
  --version "$CHART_VERSION" \
  --namespace "$NAMESPACE" \
  --values evaluation-values.yaml \
  > rendered.yaml
```

Review `rendered.yaml` for the expected hostname, ingress class, storage class,
and network selectors. It must contain digest-pinned images and must not contain
Secret values.

Check that the cluster has at least one schedulable AMD64 node:

```bash
kubectl get nodes \
  --selector kubernetes.io/arch=amd64 \
  --output wide
```

## 7. Install Hangar

```bash
helm upgrade --install "$RELEASE_NAME" \
  oci://ghcr.io/szymczag/charts/hangar \
  --version "$CHART_VERSION" \
  --namespace "$NAMESPACE" \
  --values evaluation-values.yaml \
  --rollback-on-failure \
  --wait \
  --wait-for-jobs \
  --timeout 20m
```

Do not omit `--wait-for-jobs`: the revision-scoped migration Job must finish
before the release is considered installed.

## 8. Verify the installation

Inspect the release and its resources:

```bash
helm --namespace "$NAMESPACE" status "$RELEASE_NAME"
kubectl --namespace "$NAMESPACE" get \
  deployment,statefulset,pod,job,pvc,ingress,networkpolicy
```

Find the migration Job and confirm it completed:

```bash
kubectl --namespace "$NAMESPACE" get jobs \
  --selector app.kubernetes.io/component=migrator
```

Check the public endpoint:

```bash
curl --fail --show-error --head "https://$HANGAR_HOST/"
```

Then use a browser to verify:

- `/` loads the web application;
- `/god-mode` loads the administration application;
- `/spaces` loads the public spaces application;
- API requests under `/api` succeed;
- the `/live` WebSocket connection upgrades successfully; and
- an upload can be downloaded again.

Confirm plain HTTP redirects to HTTPS and that the bundled dependency Services
are not exposed through an Ingress or external `Service`.

## 9. Protect or remove local credential files

After your secret manager contains the authoritative values, securely remove or
encrypt `evaluation-secrets.yaml`. Do not commit it, attach it to an issue, or
include it in a support archive.

Continue with [operations](operations.md) for upgrades and cleanup, or use the
[troubleshooting guide](troubleshooting.md) if the installation does not become
healthy.
