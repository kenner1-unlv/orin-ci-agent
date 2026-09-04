# Worker Dependency Policy

## Principle

The repository declares every worker dependency. Deployment resolves and validates those dependencies. A running job must not silently install packages or download executable code.

This keeps a job repeatable, prevents CUDA and JetPack incompatibilities, and makes rollback meaningful even if the Jetson temporarily has no internet access.

## Dependency classes

| Class | Strategy |
| --- | --- |
| JetPack, CUDA, drivers | Treat as target platform capabilities. Probe versions; do not modify them during routine deployment. |
| ROS 2 | Use the installed Humble distribution at `/opt/ros/humble` only for jobs that explicitly require ROS. Do not automatically source ROS for the base worker. |
| Python runtime | Use `/usr/bin/python3` (Python 3.10 on the current target). |
| Python application packages | Pin versions in the worker project and install during deployment, never during job execution. |
| Native/application packages | Declare them in a provisioning manifest and install in an explicit maintenance step with narrowly scoped elevation. |
| Models and large data | Declare name, version, expected size, checksum, and local cache path. Fetch during provisioning or an explicit prepare operation. |
| Secrets | Inject through local environment/configuration outside Git. Never bake them into releases or models. |

## Known target capabilities

Inventory captured on 2026-09-02:

- JetPack `6.2.1+b38`
- L4T `36.4.7`
- CUDA SDK `12.6.11`
- Python `3.10.12`
- ROS 2 Humble at `/opt/ros/humble`
- Custom ROS overlays at `/home/sauce/install` and `/home/sauce/lidar_imu_init_ws/install`
- Docker `29.4.2`; containerd `2.2.3`
- 61 GiB RAM and 30 GiB swap
- 27 GiB free on the 57 GiB root filesystem at inventory time
- 1.7 TiB free on the 1.8 TiB NVMe filesystem mounted at `/data`

## Storage layout

| Path | Purpose |
| --- | --- |
| `/data/persistent-worker/state` | Durable worker state |
| `/data/persistent-worker/models` | Versioned model weights and manifests |
| `/data/persistent-worker/artifacts` | Job outputs retained for inspection or delivery |
| `/data/persistent-worker/cache` | Rebuildable downloads and package/model caches |
| `~/.local/share/persistent-worker/releases` | Small, immutable application releases deployed from this repository |

The service declares `RequiresMountsFor=/data`, so it will not start against an accidental directory on the smaller root filesystem when the NVMe mount is unavailable.

The checked-in `scripts/remote-inventory.sh` command is the reproducible source for refreshing these facts.

## Runtime behavior

1. Deployment validates platform requirements before activating a release.
2. A release is immutable after activation.
3. Readiness fails clearly if a required capability is absent.
4. A job may use only capabilities declared by its versioned job contract.
5. Missing dependencies produce an actionable error; they do not trigger an implicit download.

An explicit, operator-approved `prepare` workflow may download pinned packages or model artifacts before a job is accepted.
