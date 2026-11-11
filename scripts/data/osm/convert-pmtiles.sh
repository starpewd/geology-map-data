#!/usr/bin/env bash
set -euo pipefail

input=${1:-${OSM_MBTILES:-data/osm/output/czechia.mbtiles}}
output=${2:-${OSM_PMTILES:-data/osm/output/czechia.pmtiles}}
image=${PMTILES_IMAGE:-docker.io/protomaps/go-pmtiles@sha256:a52c195560a656b8309311a7d591b90eb2c5ae55ec9111f26049371d86a22a69}
[[ -s "$input" ]] || { echo "Missing MBTiles input: $input" >&2; exit 1; }
planetiler_provenance="$input.provenance.json"
auxiliary_provenance="$input.auxiliary-provenance.json"
[[ -s "$planetiler_provenance" ]] || { echo "Missing Planetiler provenance sidecar: $planetiler_provenance" >&2; exit 1; }
[[ -s "$auxiliary_provenance" ]] || { echo "Missing auxiliary provenance sidecar: $auxiliary_provenance" >&2; exit 1; }
[[ ! -e "$output" ]] || { echo "Refusing to overwrite output: $output" >&2; exit 1; }
[[ ! -e "$output.provenance.json" ]] || { echo "Refusing to overwrite provenance: $output.provenance.json" >&2; exit 1; }
mkdir -p "$(dirname "$output")"
tmpdir=$(mktemp -d "$(dirname "$output")/.pmtiles.XXXXXX")
trap 'rm -rf "$tmpdir"' EXIT
input_abs=$(realpath "$input")
tmp_abs=$(realpath "$tmpdir")
podman run --rm --userns=keep-id -v "$input_abs:/input.mbtiles:ro" -v "$tmp_abs:/work:rw" "$image" \
  convert /input.mbtiles /work/converted.pmtiles
podman run --rm --userns=keep-id -v "$tmp_abs:/work:rw" "$image" verify /work/converted.pmtiles
[[ -s "$tmpdir/converted.pmtiles" ]] || { echo "PMTiles conversion failed" >&2; exit 1; }
mv "$tmpdir/converted.pmtiles" "$output"
mbtiles_sha256=$(sha256sum "$input" | awk '{print $1}')
planetiler_provenance_sha256=$(sha256sum "$planetiler_provenance" | awk '{print $1}')
auxiliary_provenance_sha256=$(sha256sum "$auxiliary_provenance" | awk '{print $1}')
pmtiles_sha256=$(sha256sum "$output" | awk '{print $1}')
pmtiles_version=$(podman run --rm "$image" version | sed -n 's/^pmtiles \([^,]*\).*/\1/p')
printf '{"input_mbtiles":"%s","input_sha256":"%s","planetiler_provenance":"%s","planetiler_provenance_sha256":"%s","auxiliary_provenance":"%s","auxiliary_provenance_sha256":"%s","output_sha256":"%s","pmtiles_image":"%s","pmtiles_version":"%s"}\n' \
  "$(realpath "$input")" "$mbtiles_sha256" "$(realpath "$planetiler_provenance")" "$planetiler_provenance_sha256" \
  "$(realpath "$auxiliary_provenance")" "$auxiliary_provenance_sha256" "$pmtiles_sha256" "$image" "$pmtiles_version" > "$output.provenance.json"
