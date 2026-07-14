# Deploy Hangar on Kubernetes

Hangar publishes a Helm chart for Kubernetes at:

```text
oci://ghcr.io/szymczag/charts/hangar
```

The current release is `0.1.0-rc.7`. It is qualified for evaluation on
AMD64 Kubernetes clusters. It is not yet a supported production release.

> [!IMPORTANT]
> Do not use the upstream Plane `plane-ce` chart for Hangar. It does not contain
> the Hangar images, configuration contract, security controls, or release
> evidence described here.

## Choose a deployment profile

| Profile      | Use it for                                           | Stateful services                                                       | Current status                      |
| ------------ | ---------------------------------------------------- | ----------------------------------------------------------------------- | ----------------------------------- |
| `evaluation` | Labs, demonstrations, and compatibility testing      | Bundled single-replica PostgreSQL, Valkey, RabbitMQ, and object storage | Live-qualified on AMD64             |
| `production` | Durable installations with operator-managed services | External PostgreSQL, Valkey, RabbitMQ, and S3-compatible storage        | Available for review, not supported |

Start with the [evaluation installation tutorial](evaluation-install.md) to
exercise the released chart. Use the [production installation guide](production-install.md)
only to review and help qualify the production profile.

## Compatibility

The `0.1.0-rc.7` qualification boundary is:

| Item                   | Qualified boundary                                               |
| ---------------------- | ---------------------------------------------------------------- |
| Kubernetes             | 1.30 through 1.36, including 1.36.2                              |
| Helm                   | 4.2                                                              |
| Node architecture      | `linux/amd64`                                                    |
| Pod Security Admission | Restricted                                                       |
| Ingress                | TLS-enabled controller with WebSocket support                    |
| Networking             | A CNI that enforces `NetworkPolicy`                              |
| Storage                | A default `StorageClass`, or explicit evaluation storage classes |

The chart does not install an ingress controller, cert-manager, a CNI, a CSI
driver, an external secret operator, or observability infrastructure.

## Secure email delivery

Secure email delivery is disabled by default. When `mail.enabled=true`, the
chart adds a dedicated `mail-worker` for Amazon SES API delivery, feedback
processing, audit receipts, suppression handling, and optional OpenPGP
encryption. The workload is isolated from the general workers and is the only
application pod that receives the mail service account or optional SES and SQS
credentials.

Before enabling it, an operator must provide a verified SES identity, DKIM and
DMARC DNS records, production SES access, configuration sets, an SNS topic, an
SQS queue, least-privilege IAM, and the `hangar-mail` Secret. The chart does not
create or validate those AWS resources.

Use the [configuration reference](configuration.md#secure-email-delivery) for
the Helm values and Secret contract. Follow the
[Amazon SES operations guide](../aws-ses-email-operations.md) for provisioning,
rollout, deliverability monitoring, suppression recovery, and incidents. The
[email security model](../email-delivery-and-openpgp.md) explains data handling,
retention, and OpenPGP policy.

## Release identity

The product, chart, and Git identifiers are deliberately different:

| Identifier         | Current value                               |
| ------------------ | ------------------------------------------- |
| Product version    | `v0.1.0-rc.7`                               |
| Helm chart version | `0.1.0-rc.7`                                |
| Git tag            | `hangar-v0.1.0-rc.7`                        |
| OCI chart          | `ghcr.io/szymczag/charts/hangar:0.1.0-rc.7` |

`rc.1` and `rc.2` were consumed by incomplete publication attempts. Do not use
them. `rc.6` is the previous complete release. Published versions are immutable
and are never repaired in place.

## Documentation

- [Install the evaluation profile](evaluation-install.md) — complete a first
  installation in a dedicated namespace.
- [Prepare the production profile](production-install.md) — configure external
  services and review the unsupported production path.
- [Configuration reference](configuration.md) — understand values, Secrets,
  routes, workloads, storage, and networking.
- [Operations](operations.md) — verify, upgrade, rotate credentials, back up,
  restore, roll back, and uninstall.
- [Security and artifact verification](security.md) — understand the security
  model and verify checksums, attestations, signatures, and anonymous access.
- [Troubleshooting](troubleshooting.md) — diagnose common installation and
  runtime failures without collecting credentials.
- [Chart source](../../charts/hangar/README.md) — chart-maintainer entry point.
- [Delivery and qualification plan](../kubernetes-deployment-plan.md) — normative
  requirements and remaining release gates.

## Support boundary

The evaluation profile passed an ephemeral-cluster exercise covering Restricted
Pod Security, migrations, HTTPS ingress, WebSockets, positive and negative
network-policy checks, dependency connectivity, object-storage persistence, an
atomic upgrade, rollback-on-failure behavior, uninstall, and retained PVCs.

The public `rc.7` chart archive, OCI chart, and digest-pinned Hangar images are
anonymously downloadable. The release workflow also created provenance
attestations and keyless Cosign signatures.

Production support remains blocked on production-profile installation and
application-flow testing, coordinated backup and restore, migration-failure
recovery, vulnerability and license review, and a completed support matrix. See
the [qualification checklist](../kubernetes-deployment-plan.md#release-qualification-checklist)
for the authoritative gate status.
