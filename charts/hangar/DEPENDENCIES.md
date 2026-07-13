# Evaluation dependency record

This file records the resolved dependencies for Hangar chart `0.1.0-rc.2`.
The evaluation profile is for non-critical testing. These records do not turn
single-replica dependencies into a production availability recommendation.

## Helm dependencies

| Alias                   | Upstream chart | Version | Repository                                   | Packaged chart SHA-256                                             |
| ----------------------- | -------------- | ------: | -------------------------------------------- | ------------------------------------------------------------------ |
| `evaluation-postgresql` | `postgres`     |   1.6.4 | `https://groundhog2k.github.io/helm-charts/` | `0403591e1768cffa4d01500bf029cddc0cda6cb944ff1f241981c1670a97e60b` |
| `evaluation-rabbitmq`   | `rabbitmq`     |   2.3.2 | `https://groundhog2k.github.io/helm-charts/` | `46a7b77988e265d1f62b235d975fdb11a976f89760e57d1c694b72ac142da575` |
| `evaluation-valkey`     | `valkey`       |   2.3.1 | `https://groundhog2k.github.io/helm-charts/` | `e768851e8437db0372ce46aaa63e3244373c06d987a67b690915e6b78f360c20` |

`Chart.lock` pins dependency versions and repositories. CI resolves that lock
against the vendored archives and verifies each archive's exact SHA-256 without
requiring a repository index or selecting a newer dependency.

## Resolved evaluation images

Evaluation workloads are constrained to `linux/amd64`, and image references use
the corresponding platform manifest digest.

| Workload              | Image                                | Immutable amd64 digest                                                    |
| --------------------- | ------------------------------------ | ------------------------------------------------------------------------- |
| PostgreSQL            | `docker.io/postgres:18.4`            | `sha256:0c49c0c906cb405ea65e70c284570fee91c7750ca9336369afc0edf4fce211db` |
| RabbitMQ              | `docker.io/rabbitmq:4.3.1`           | `sha256:11846d5a067c15c0f260d6c387263e34972b884a6e711561608753c22fca5221` |
| RabbitMQ init         | `docker.io/busybox:stable`           | `sha256:b7f3d86d6e84fc17718c48bcde1450807faa2d56704205c697b4bd5df7b9e29f` |
| Valkey                | `docker.io/valkey/valkey:9.1.0`      | `sha256:e30fbdc8d6d6b355712e50f4008321026f69db3e450254b4f0008d22745d8d0e` |
| SeaweedFS `weed mini` | `docker.io/chrislusf/seaweedfs:4.39` | `sha256:1f4d22c98089dba5e849ea3a1f24a7d85b3177ab39a8d9a70275856882ce2be3` |

## Validation and signing toolchain

| Tool        | Pinned release or image                                                                                |
| ----------- | ------------------------------------------------------------------------------------------------------ |
| Helm        | `v4.2.0` through `azure/setup-helm@9bc31f4ebc9c6b171d7bfbaa5d006ae7abdb4310`                           |
| kubeconform | `ghcr.io/yannh/kubeconform@sha256:7426d17ca19f3731d2a6287c868005f052f2682800141f20e83d3109f5c8faa1`    |
| kube-linter | `ghcr.io/stackrox/kube-linter@sha256:94644f35948465a70b2dd1526a80522d1a1f26499f783b1eff21618dda1fd4dd` |
| Cosign      | `v3.0.6` through `sigstore/cosign-installer@6f9f17788090df1f26f669e9d70d6ae9567deba6`                  |

All GitHub Actions used by chart validation and publication are pinned to full
commit SHAs in their workflow files.

## Qualification notes

- Dependency management interfaces are disabled or remain cluster-internal.
- Every dependency uses persistent storage; StatefulSet claim retention is
  `Retain` where the upstream chart exposes that control.
- The evaluation object store is a chart-owned, single-node `weed mini`
  StatefulSet. It consumes caller-managed credentials directly and does not
  render a random Helm-managed Secret.
- No dependency receives Kubernetes RBAC. Service-account token automounting is
  disabled.
- All rendered containers use a read-only root filesystem, non-root identity,
  dropped Linux capabilities, `RuntimeDefault` seccomp, and resource requests
  and limits.
- The release gate must still perform vulnerability, license, and image-policy
  review for the exact digests above. A dependency upgrade requires updating
  this record, the lock file, render evidence, and recovery-test evidence.
