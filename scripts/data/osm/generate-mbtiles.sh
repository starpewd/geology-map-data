#!/usr/bin/env bash
set -euo pipefail

input=${1:-${OSM_PBF:-data/osm/input/czech-republic-latest.osm.pbf}}
output=${2:-${OSM_MBTILES:-data/osm/output/czechia.mbtiles}}
auxiliary_dir=${3:-${OSM_AUX_DIR:-data/osm/auxiliary}}
threads=${THREADS:-$(getconf _NPROCESSORS_ONLN)}
maxzoom=${MAXZOOM:-14}
image=${PLANETILER_IMAGE:-docker.io/openmaptiles/planetiler-openmaptiles@sha256:a5d93e943f193ec0b0e5a93f45d01854caee1a0dc2c26124028a9665cd6ea8ec}
profile_revision=${OPENMAPTILES_PROFILE_REVISION:-unknown}
profile_schema=${OPENMAPTILES_SCHEMA_VERSION:-unknown}
[[ -s "$input" ]] || { echo "Missing PBF input: $input" >&2; exit 1; }
[[ -d "$auxiliary_dir" ]] || { echo "Missing auxiliary data directory: $auxiliary_dir; run prepare-auxiliary.py first" >&2; exit 1; }
[[ ! -e "$output" ]] || { echo "Refusing to overwrite output: $output" >&2; exit 1; }
[[ ! -e "$output.provenance.json" ]] || { echo "Refusing to overwrite provenance: $output.provenance.json" >&2; exit 1; }
[[ ! -e "$output.auxiliary-provenance.json" ]] || { echo "Refusing to overwrite auxiliary provenance: $output.auxiliary-provenance.json" >&2; exit 1; }
input_abs=$(realpath "$input")
auxiliary_abs=$(realpath "$auxiliary_dir")
python3 "$(dirname "$0")/verify-auxiliary.py" "$auxiliary_abs" "$image"
mkdir -p "$(dirname "$output")"
tmpdir=$(mktemp -d "$(dirname "$output")/.planetiler.XXXXXX")
trap 'rm -rf "$tmpdir"' EXIT
tmp_abs=$(realpath "$tmpdir")
planetiler_tmpdir=/work/tmp
node_db=$planetiler_tmpdir/node.db
multipolygon_db=$planetiler_tmpdir/multipolygon.db
feature_db=$planetiler_tmpdir/feature.db
for temp_path in "$node_db" "$multipolygon_db" "$feature_db"; do
  [[ "$temp_path" == "$planetiler_tmpdir/"* ]] || { echo "Temporary database path is outside the mounted temporary directory: $temp_path" >&2; exit 1; }
done
printf 'Planetiler temporary paths: tmpdir=%s node=%s multipolygon=%s feature=%s (host mount %s)\n' \
  "$planetiler_tmpdir" "$node_db" "$multipolygon_db" "$feature_db" "$tmp_abs"
version_output=$(podman run --rm "$image" --version 2>&1)
planetiler_version=$(printf '%s\n' "$version_output" | sed -n 's/.*Planetiler build version: //p' | tail -n 1)
planetiler_build=$(printf '%s\n' "$version_output" | sed -n 's/.*Planetiler build git hash: //p' | tail -n 1)
[[ -n "$planetiler_version" && -n "$planetiler_build" ]] || { echo "Could not identify Planetiler version/build from image" >&2; exit 1; }
podman run --rm --userns=keep-id -v "$input_abs:/input/czechia.osm.pbf:ro" \
  -v "$auxiliary_abs:/aux:ro" -v "$tmp_abs:/work:rw" \
  "$image" --osm_path=/input/czechia.osm.pbf --output=/work/czechia.mbtiles \
  --natural_earth_path=/aux/natural_earth \
  --lake_centerlines_path=/aux/lake_centerline.parquet \
  --water_polygons_path=/aux/water_polygons.parquet \
  --download_natural_earth=false --download_lake_centerlines=false --download_water_polygons=false \
  --tmpdir="$planetiler_tmpdir" --temp_nodes="$node_db" \
  --temp_multipolygons="$multipolygon_db" --temp_features="$feature_db" \
  --tile_format=mvt --maxzoom="$maxzoom" --render_maxzoom="$maxzoom" \
  --threads="$threads" --download=false
[[ -s "$tmpdir/czechia.mbtiles" ]] || { echo "Planetiler did not produce MBTiles" >&2; exit 1; }
mv "$tmpdir/czechia.mbtiles" "$output"
cp "$auxiliary_abs/manifest.json" "$output.auxiliary-provenance.json"
python3 - "$output.provenance.json" "$output" "$input_abs" "$auxiliary_abs/manifest.json" \
  "$image" "$planetiler_version" "$planetiler_build" "$profile_revision" "$profile_schema" "$maxzoom" "$threads" <<'PY'
import hashlib, json, sys
from pathlib import Path
out, mbtiles, pbf, auxiliary, image, version, build, revision, schema, maxzoom, threads = sys.argv[1:]
def digest(path):
    value = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()
Path(out).write_text(json.dumps({
    "source_pbf": pbf,
    "source_sha256": digest(pbf),
    "auxiliary_manifest": str(Path(auxiliary).resolve()),
    "auxiliary_manifest_sha256": digest(auxiliary),
    "planetiler_image": image,
    "planetiler_version": version,
    "planetiler_build": build,
    "profile_revision": revision,
    "profile_schema_version": schema,
    "tile_format": "mvt",
    "output_format": "mbtiles",
    "output_sha256": digest(mbtiles),
    "minzoom": 0,
    "maxzoom": int(maxzoom),
    "render_maxzoom": int(maxzoom),
    "threads": int(threads),
    "download": False,
    "temporary_paths": {
        "tmpdir": "/work/tmp",
        "node_db": "/work/tmp/node.db",
        "multipolygon_db": "/work/tmp/multipolygon.db",
        "feature_db": "/work/tmp/feature.db",
    },
}, indent=2) + "\n")
PY
