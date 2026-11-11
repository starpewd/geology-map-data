#!/usr/bin/env bash
set -euo pipefail

planetiler_image=${PLANETILER_IMAGE:-docker.io/openmaptiles/planetiler-openmaptiles@sha256:a5d93e943f193ec0b0e5a93f45d01854caee1a0dc2c26124028a9665cd6ea8ec}
pmtiles_image=${PMTILES_IMAGE:-docker.io/protomaps/go-pmtiles@sha256:a52c195560a656b8309311a7d591b90eb2c5ae55ec9111f26049371d86a22a69}

command -v podman >/dev/null || { echo "podman is required" >&2; exit 1; }
command -v podman-compose >/dev/null || { echo "podman-compose is required" >&2; exit 1; }
podman --version
podman-compose --version

for image in "$planetiler_image" "$pmtiles_image"; do
  podman image inspect "$image" --format '{{.RepoTags}} {{.RepoDigests}}'
done
podman run --rm "$planetiler_image" --version 2>&1 | grep -E 'Planetiler build (version|git hash|timestamp)'
podman run --rm "$pmtiles_image" version
podman run --rm "$pmtiles_image" --help | sed -n '1,100p'
