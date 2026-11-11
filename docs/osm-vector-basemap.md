# Czechia offline OpenStreetMap vector basemap pipeline

This is a preparation workflow. It does not create or publish a Czechia archive
unless an operator explicitly runs the fetch and build commands below. Keep
build inputs and outputs outside Git; no OSM package is registered in
`map_catalog.json` yet. Dataset identity, version, distribution URL, size, and
catalog metadata require a separate release decision under the current
[catalogue contract](dataset-contract.md).

## Inputs and tools

The source is Geofabrik's rolling Czech Republic extract:
`https://download.geofabrik.de/europe/czech-republic-latest.osm.pbf`. The fetch
script records the exact URL, UTC retrieval time, HTTP Last-Modified/ETag when
provided, and SHA-256 alongside the file. The URL is mutable; the recorded hash
and timestamp identify the bytes actually used.

The configured images should be pinned by digest for a release build. The
images observed in the preparation environment were:

| Tool | Observed version/capability | Image digest |
| --- | --- | --- |
| Planetiler OpenMapTiles | Planetiler `0.10.3-SNAPSHOT`, build `45d5c0395dc4d1e93e52e2e64f958bd28a556e5a`; accepts `--tile_format=mvt`, defaults to MBTiles | `docker.io/openmaptiles/planetiler-openmaptiles@sha256:a5d93e943f193ec0b0e5a93f45d01854caee1a0dc2c26124028a9665cd6ea8ec` |
| go-pmtiles | `v1.31.2`; `convert`, in-place `cluster`, `verify`, `show`; MBTiles conversion supported | `docker.io/protomaps/go-pmtiles@sha256:a52c195560a656b8309311a7d591b90eb2c5ae55ec9111f26049371d86a22a69` |
| OpenMapTiles tools | Local image tag `7.2` present; not required by the scripts | `docker.io/openmaptiles/openmaptiles-tools@sha256:d7ea1281420eebf2ed0cfc704917026a838f73bdae42a4f877323a00785e1046` |

Podman is 6.1.3 and podman-compose is 1.6.0. The Planetiler image digest pins
the profile revision. Record the profile/schema version and build parameters
with each build. Review image digest updates deliberately; do not silently
rebuild an existing dataset version using mutable `latest` tags.
The generated style/fonts from `/home/jiri/develop/_tools/openmaptiles` are a
read-only reference input. If regenerating them with that repository's Compose
workflow, run it with `PODMAN_COMPOSE_IN_POD=false PODMAN_USERNS=keep-id`.

## Commands

Run from the data repository root. Paths may be supplied positionally or
through environment variables shown below. Scripts refuse to overwrite inputs
and final outputs. Intermediate files use private temporary directories and
are removed on exit.

```sh
# Check container tools, local image digests, and CLI versions/capabilities.
bash scripts/data/osm/check-tools.sh

# Fetch the current Geofabrik extract (downloads the large PBF).
bash scripts/data/osm/fetch-czechia.sh [OUTPUT_DIR]
# Or set OSM_INPUT_DIR=/mnt/osm/input

# Obtain 24 profile auxiliary files into persistent storage and record each
# source URL/revision status, retrieval time, size, ETag and SHA-256.
python3 scripts/data/osm/prepare-auxiliary.py data/osm/auxiliary

# Generate MVT in MBTiles using the local input PBF.
OSM_PBF=data/osm/input/czech-republic-latest.osm.pbf \
OSM_MBTILES=data/osm/output/czechia.mbtiles OSM_AUX_DIR=data/osm/auxiliary \
MAXZOOM=14 THREADS=8 bash scripts/data/osm/generate-mbtiles.sh [PBF] [OUTPUT_MBTILES] [AUX_DIR]

# Convert MBTiles to PMTiles and verify archive structure.
bash scripts/data/osm/convert-pmtiles.sh [INPUT.mbtiles] [OUTPUT.pmtiles]

# Validate PMTiles integrity, MVT format, bounds, zoom range and core layers.
bash scripts/data/osm/validate-archive.sh data/osm/output/czechia.pmtiles

# Package the locally generated style, sprite scales, and glyph PBFs.
python3 scripts/data/osm/prepare-style.py \
  /path/to/openmaptiles/build/style /path/to/openmaptiles/data/fonts \
  data/osm/output/style --license-file /path/to/openmaptiles/LICENSE.md \
  --source-repository /path/to/openmaptiles --font-package-release v2.0
```

Scripts default to the image digests listed above. Image overrides are
`PLANETILER_IMAGE` and `PMTILES_IMAGE`. Generation accepts `MAXZOOM` and
`THREADS`. For a
pinned build use digest references, e.g.:

```sh
PLANETILER_IMAGE=docker.io/openmaptiles/planetiler-openmaptiles@sha256:a5d93e943f193ec0b0e5a93f45d01854caee1a0dc2c26124028a9665cd6ea8ec \
PMTILES_IMAGE=docker.io/protomaps/go-pmtiles@sha256:a52c195560a656b8309311a7d591b90eb2c5ae55ec9111f26049371d86a22a69 \
bash scripts/data/osm/generate-mbtiles.sh
```

Planetiler's installed OpenMapTiles profile accepts `tile_format=mvt` and emits
MBTiles by default. The workflow explicitly selects MVT (never MLT), converts
with `go-pmtiles convert`, then verifies the result. The installed converter
reports that its MBTiles output is already clustered; running `cluster` again
fails with “archive is already clustered,” so the pipeline does not invoke it
redundantly. The standalone cluster command remains available if a later input
archive needs repacking.

`prepare-auxiliary.py` uses the Natural Earth ZIP URL list and exact Parquet
URLs reported by the pinned Planetiler image (`lake_centerline.parquet` and
`water_polygons.parquet`). It validates every ZIP member or Parquet magic and
writes the files
and `manifest.json` into a persistent directory by staging a temporary sibling
and renaming only after success. Source endpoints do not expose immutable
revisions in the pinned profile; manifest entries explicitly mark the revision
unknown and record the exact URL, retrieval UTC, Last-Modified/ETag when
provided, size, and SHA-256. The hash identifies the retrieved bytes. The script
refuses to replace an existing directory; refresh into a new directory and
review the hashes first.

Before starting Planetiler, generation runs `verify-auxiliary.py` against every
expected file and provenance record, including the Planetiler image identity,
source URL/path, retrieval timestamp, size, and SHA-256. It mounts the auxiliary
directory read-only and passes `--download=false` plus the source-specific
download switches as `false`. Missing or changed inputs stop the build. The
required mounted paths are `natural_earth/`, `lake_centerline.parquet`, and
`water_polygons.parquet`; the OSM PBF remains a separately supplied local
input.

The image reports the Parquet inputs at
`https://planetiler.onthegomap.com/lake_centerline.parquet` and
`https://planetiler.onthegomap.com/water_polygons.parquet`; its Natural Earth
ZIP URL list is in `scripts/data/osm/auxiliary-sources.json`. Natural Earth ZIPs
are retained under `source-archives/natural_earth/` and extracted to
`natural_earth/`, with hashes for original archives and extracted files. These
endpoints do not expose immutable revisions, so revision fields remain
explicitly unknown and SHA-256 values identify the exact inputs.

Planetiler temporary storage is mounted at `/work` from the script's private
host-side temporary directory. The script sets `--tmpdir=/work/tmp`,
`--temp_nodes=/work/tmp/node.db`,
`--temp_multipolygons=/work/tmp/multipolygon.db`, and
`--temp_features=/work/tmp/feature.db`; it prints and checks these resolved
container paths before launch. The private directory is removed on exit. Only
the final MBTiles and provenance sidecars are retained.

## Provenance and validation

Keep source `.provenance`, MBTiles `.provenance.json`, the adjacent
`.auxiliary-provenance.json`, final PMTiles SHA-256, container digests,
Planetiler version/build hash, zoom/threads and overrides with each candidate
build. Auxiliary provenance includes all source URLs, revision availability,
retrieval times, hashes, sizes and response validators when provided. The
profile revision and schema version are intentionally recorded as `unknown` by
default; an image digest pins the exact executable and bundled profile
contents, but does not identify the profile source commit or schema version.
Verify those against the pinned profile before
production. The profile's optional Wikidata translations are disabled by
default (`fetch_wikidata=false`); if enabled later, pin and record that input
separately.

`validate-archive.sh` checks PMTiles archive structure, MVT/PBF tile format,
Czechia-scale bounds, zoom fields and a nonempty vector layer list containing
the expected core OpenMapTiles layers. `EXPECTED_LAYERS` overrides the
comma-separated layer list after an intentional profile-schema change. This
does not decode every tile payload. Before publication, inspect representative
tile payloads and render the package in MapLibre.

## Build resource estimate

The current Geofabrik page lists the Czech PBF at about 0.9 GB (the rolling
extract changes over time). Planetiler's upstream guidance is 5–10 times the
input size plus 1 GB of free SSD for ordinary builds, with 0.5 times input size
as a baseline free-RAM amount; OpenMapTiles' own quickstart cites roughly
15 GB disk and 3–8 GB RAM for small extracts. For this workflow, reserve at
least 20 GB free disk for input, intermediate files, output conversion and
auxiliary inputs, and use 8 GB RAM minimum or 16 GB for headroom. Higher zooms,
more retained intermediates, concurrent jobs, or added source data need more.
These are planning estimates, not a guarantee; retain Planetiler's own resource
warnings and check the actual extract size before a future build. Sources:
[Geofabrik Czech Republic extract](https://download.geofabrik.de/europe/czech-republic.html),
[Planetiler resource guidance](https://github.com/onthegomap/planetiler/blob/main/README.md),
[OpenMapTiles quickstart](https://github.com/openmaptiles/openmaptiles/blob/master/QUICKSTART.md).

## Offline style and app consumption

`prepare-style.py` emits `style.template.json`, deliberately not a directly
loadable runtime style. It uses named placeholders for the PMTiles URI, sprite
base URI, and glyph template. `style-template-manifest.json` gives their
required Android MapLibre Native forms and requires loading the style JSON
itself from its absolute filesystem path. At runtime substitute
`pmtiles://file:///absolute/path/to/czechia.pmtiles`,
`file:///absolute/path/to/style/sprite`, and
`file:///absolute/path/to/style/fonts/{fontstack}/{range}.pbf`. The sprite value
is the base URI; Native appends scale and extensions. Use absolute local paths,
not relative paths or `asset://` resources.

The preparer copies both sprite scales, every generated font-stack glyph PBF,
and the OpenMapTiles license notice. It records the exact OpenMapTiles Git
commit, working-tree changes, generated style hash, font package release,
official archive SHA-256 when available, a deterministic hash of the packaged
font tree, and notices included. The local OpenMapTiles Makefile points to
fonts release `v2.0`; its source ZIP is not retained, so that archive checksum
is unknown. The tree hash identifies the exact local glyph files. The current
font directory has no license notice, so the manifest records that font
notices are absent and must be obtained before distribution. Auxiliary data
licenses require separate review and inclusion with the dataset package.

At this preparation review, the style source checkout was at commit
`6c11838d38030148832c039c2ea367274db86a87`. The font release URL is
`https://github.com/openmaptiles/fonts/releases/download/v2.0/noto-open-sans.zip`.
The local font-tree SHA-256 was
`fc22d9f3dc0fd9bdad4da5fbe34ea33c6c3022ed98f47a2a27d68987e74e2df1`; this is
not the missing source archive checksum. Each generated manifest records the
commit, worktree state, and actual font-tree hash at packaging time.

The style package includes `ATTRIBUTION.md` and `OPENMAPTILES-LICENSE.md`.
Attribution links in the style are descriptive and do not cause resource
requests. Android `maplibre_gl` supports PMTiles natively; app work remains to
substitute the placeholders and resolve local absolute paths at runtime. No
custom PMTiles protocol registration is required.

This OpenMapTiles-derived cartography is a practical OSM Carto-like starting
point, not pixel-identical OSM Carto. Symbol placement, tags, fonts, and
rendering engines differ.

## Licensing and attribution

- **OpenStreetMap source data:** ODbL 1.0. Attribute visibly as
  `© OpenStreetMap contributors` and link to
  <https://www.openstreetmap.org/copyright>. Review and meet ODbL attribution
  and share-alike obligations for derived databases. Geofabrik extract access
  does not grant different redistribution terms.
- **OpenMapTiles schema/style:** inspect the exact profile and style notices
  used. The local reference repository's `LICENSE.md` separates BSD-3-Clause
  code/schema terms from CC-BY-4.0 cartographic design terms and requests
  visible OpenMapTiles credit. Include `© OpenMapTiles` linked to
  <https://openmaptiles.org/> where applicable and retain required notices.
- **Fonts:** generated stacks include Open Sans and Noto Sans. Preserve their
  font licenses/notices (commonly SIL Open Font License); confirm exact files
  and notices from the checked-out source before redistribution.
- **Auxiliary data:** Natural Earth, Wikidata-derived names, water polygons,
  and lake centerlines can have separate terms and attribution. Inventory the
  exact inputs and licenses per build; do not assume they share ODbL.

The app's GPL-3.0-or-later source license does not replace data, style, font,
or auxiliary-data terms. Redistribution requires a reviewed notice bundle and
confirmation that the selected source inputs and transformations may be
redistributed.
