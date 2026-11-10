# Dataset catalogue contract

`map_catalog.json` is the authoritative package manifest for the current
distribution model. Its root integer `schemaVersion` is `2` and `datasets` is
an array.
There is no per-dataset manifest: dataset metadata and the complete file list
already live in this catalogue, so another manifest would duplicate mutable
metadata. Introduce one only if a future transport/package format needs metadata
that cannot be represented in the catalogue.

Every dataset has a stable lowercase `id` matching
`^[a-z0-9][a-z0-9._-]{0,63}$`, nonempty `name`, `description`, `kind`, `source`,
and `license`, boolean `available`, nonnegative `sizeBytes`, `version`, and a
`files` array. IDs are unique across the catalogue and are used as local
installation directory names; do not change an ID to rename a dataset.

Available datasets use a nonempty version identifier containing only letters,
digits, `.`, `_`, `+`, and `-` (maximum 128 characters), and at least one file.
Unavailable entries use an empty version, zero size, and an empty file list.
For available entries, `sizeBytes` equals the sum of file sizes. Each file has
a unique safe relative `name`, absolute HTTPS `url`, positive integer
`sizeBytes`, and a 64-character hexadecimal SHA-256. Relative names use `/`
separators and cannot be absolute, contain Windows drive prefixes or backslash
separators, or contain empty, `.` or `..` segments. File paths cannot conflict
with one another as file/directory prefixes or use the reserved root
`installation.json` path. The relative name is preserved beneath the installed
dataset directory.

`source` records attribution and `license` identifies the applicable data
licence/terms. These fields describe provenance; they do not grant permission
to redistribute. `compatibility` and `metadata` are optional JSON objects for
constraints and type-specific format details (for example a PMTiles format
version). Known `appMinVersion` and `appMaxVersion` values use stable
`major.minor.patch` versions without prerelease/build suffixes, and the minimum
cannot exceed the maximum. The app validates their format and order but does
not compare them to its own version. Add optional keys rather than duplicating
the common contract; producers must document additional keys and consumers
must add explicit checks before relying on them.

An available dataset version identifies immutable content. If any file bytes,
metadata that affects interpretation, or file list changes, publish a new
version and stable URL. Avoid `main` URLs for production releases; use a
versioned release asset or commit-pinned URL. The test asset URL is pinned to
the commit containing the exact PMTiles bytes.

The app validates catalogue schema and entries before displaying them, then
checks each downloaded file's declared size (when known) and SHA-256 before
installation. The catalogue does not assert application decoding validity; format-specific
validators should be added when production formats are introduced.

Validate the checked-in catalogue and any repository-hosted raw assets from
this repository root:

```sh
python3 scripts/validate_catalog.py
```

When adding a dataset, use a new stable ID only for a new logical dataset, assign
a new content version identifier, list every required relative file with its published
HTTPS URL/size/hash, set the total size, record attribution and licence terms,
and add compatibility or format metadata only when applicable. Run the
validator before publishing. Do not publish transformed third-party data until
redistribution rights are established.

## CI and local validation

`Dataset Repository CI` runs on pull requests targeting `main`, pushes to
`main`, and manual dispatch. It validates JSON syntax, Python syntax for the
validator, then runs `python3 scripts/validate_catalog.py`. The validator checks
the catalogue and locally available repository-hosted assets against declared
sizes and SHA-256 hashes. The workflow does not download production datasets.
Inspect run logs from the repository's **Actions** tab; pull request runs are
also linked under **Checks**.

Run the same checks locally from the data repository root:

```sh
python3 -m json.tool map_catalog.json > /dev/null
python3 -m py_compile scripts/validate_catalog.py
python3 scripts/validate_catalog.py
```

The app has a separate workflow and repository history. Merging a data change
does not trigger application CI. To rerun app integration against the current
data `main`, open **Actions** in `geology-map`, select **Application CI**, choose
**Run workflow** on branch `main`, and start it. The application workflow
checks out the current public data `main` without credentials.
