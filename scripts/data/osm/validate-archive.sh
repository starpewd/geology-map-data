#!/usr/bin/env bash
set -euo pipefail
archive=${1:?Usage: validate-archive.sh ARCHIVE.pmtiles}
expected_layers=${EXPECTED_LAYERS:-boundary,building,housenumber,landcover,landuse,mountain_peak,park,place,poi,transportation,transportation_name,water,water_name}
image=${PMTILES_IMAGE:-docker.io/protomaps/go-pmtiles@sha256:a52c195560a656b8309311a7d591b90eb2c5ae55ec9111f26049371d86a22a69}
[[ -s "$archive" ]] || { echo "Archive is missing or empty: $archive" >&2; exit 1; }
tmpdir=$(mktemp -d)
trap 'rm -rf "$tmpdir"' EXIT
archive_abs=$(realpath "$archive")
podman run --rm --userns=keep-id -v "$archive_abs:/archive.pmtiles:ro" "$image" verify /archive.pmtiles
podman run --rm --userns=keep-id -v "$archive_abs:/archive.pmtiles:ro" "$image" show --metadata /archive.pmtiles > "$tmpdir/metadata.json"
podman run --rm --userns=keep-id -v "$archive_abs:/archive.pmtiles:ro" "$image" show --header-json /archive.pmtiles > "$tmpdir/header.json"
python3 - "$tmpdir/metadata.json" "$tmpdir/header.json" "$expected_layers" <<'PY'
import json
import sys
from pathlib import Path
metadata = json.loads(Path(sys.argv[1]).read_text())
header = json.loads(Path(sys.argv[2]).read_text())
expected = set(filter(None, sys.argv[3].split(',')))
layers = {item['id'] for item in metadata.get('vector_layers', []) if isinstance(item, dict) and 'id' in item}
missing = expected - layers
if metadata.get('format') not in ('pbf', 'mvt'):
    raise SystemExit(f"Expected MVT/pbf tiles, got format={metadata.get('format')!r}")
if header.get('tile_type') != 'mvt':
    raise SystemExit(f"Expected PMTiles MVT tile_type, got {header.get('tile_type')!r}")
if not layers:
    raise SystemExit('PMTiles metadata has no vector_layers')
if missing:
    raise SystemExit(f"Missing expected OpenMapTiles layers: {', '.join(sorted(missing))}")
bounds = header.get('bounds')
if isinstance(bounds, list):
    values = [float(v) for v in bounds]
elif isinstance(bounds, str):
    values = [float(v) for v in bounds.split(',')]
else:
    raise SystemExit(f"Could not read archive bounds from header: {bounds!r}")
if len(values) != 4 or not (11 <= values[0] <= 14 and 17 <= values[2] <= 21 and 47 <= values[1] <= 50 and 50 <= values[3] <= 53):
    raise SystemExit(f"Bounds do not appear to cover Czechia: {bounds}")
if 'minzoom' not in header or 'maxzoom' not in header:
    raise SystemExit('PMTiles header is missing minzoom/maxzoom')
minzoom, maxzoom = int(header['minzoom']), int(header['maxzoom'])
if not 0 <= minzoom <= maxzoom <= 16:
    raise SystemExit(f"Invalid PMTiles zoom range: {minzoom}-{maxzoom}")
print(f"Validated format={metadata['format']}, layers={len(layers)}, bounds={bounds}")
PY
