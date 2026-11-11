#!/usr/bin/env bash
set -euo pipefail

output_dir=${1:-${OSM_INPUT_DIR:-data/osm/input}}
url=${OSM_PBF_URL:-https://download.geofabrik.de/europe/czech-republic-latest.osm.pbf}
mkdir -p "$output_dir"
output="$output_dir/czech-republic-latest.osm.pbf"
if [[ -e "$output" ]]; then
  echo "Refusing to overwrite existing input: $output" >&2
  exit 1
fi
[[ ! -e "$output.provenance" ]] || { echo "Refusing to overwrite existing provenance: $output.provenance" >&2; exit 1; }
tmp=$(mktemp "$output_dir/.czech-republic.XXXXXX")
trap 'rm -f "$tmp" "$tmp.headers"' EXIT
curl --fail --location --retry 3 --dump-header "$tmp.headers" --output "$tmp" "$url"
[[ -s "$tmp" ]] || { echo "Downloaded file is empty" >&2; exit 1; }
timestamp=$(date -u +%Y-%m-%dT%H:%M:%SZ)
sha256=$(sha256sum "$tmp" | awk '{print $1}')
size_bytes=$(wc -c < "$tmp" | tr -d ' ')
mv "$tmp" "$output"
{
  printf 'source_url=%s\n' "$url"
  printf 'downloaded_at_utc=%s\n' "$timestamp"
  printf 'sha256=%s\n' "$sha256"
  printf 'size_bytes=%s\n' "$size_bytes"
  awk 'BEGIN{IGNORECASE=1} /^Last-Modified:|^ETag:/ {gsub("\r", ""); print}' "$tmp.headers"
} > "$output.provenance"
echo "Saved $output ($sha256)"
