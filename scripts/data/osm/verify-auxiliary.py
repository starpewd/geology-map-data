#!/usr/bin/env python3
"""Verify all required auxiliary inputs against their retained provenance."""
import argparse
import hashlib
import json
import zipfile
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
NATURAL_EARTH_PROFILE_DIR = Path("source-archives/natural_earth")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("auxiliary_dir", type=Path)
    parser.add_argument("planetiler_image")
    parser.add_argument("--source-list", type=Path, default=SCRIPT_DIR / "auxiliary-sources.json")
    args = parser.parse_args()
    root = args.auxiliary_dir.resolve(strict=True)
    manifest = json.loads((root / "manifest.json").read_text())
    if manifest.get("planetiler_image") != args.planetiler_image:
        raise SystemExit("Auxiliary inputs were prepared for a different Planetiler image")
    expected = json.loads(args.source_list.read_text())["sources"]
    records = manifest.get("sources")
    if not isinstance(records, list) or len(records) != len(expected):
        raise SystemExit("Auxiliary provenance manifest is incomplete")
    by_id = {record.get("id"): record for record in records}
    if len(by_id) != len(expected):
        raise SystemExit("Auxiliary provenance has missing or duplicate source IDs")
    natural_earth_sources = [item for item in expected if item["id"].startswith("natural_earth_")]
    expected_profile_archives = set()
    for definition in expected:
        record = by_id.get(definition["id"])
        if record is None or any(record.get(key) != definition.get(key) for key in ("path", "url", "revision")):
            raise SystemExit(f"Auxiliary source definition mismatch: {definition['id']}")
        if record.get("format") != definition.get("format", "zip"):
            raise SystemExit(f"Auxiliary format mismatch: {definition['id']}")
        if not record.get("retrieved_at_utc") or not record.get("revision_note"):
            raise SystemExit(f"Auxiliary retrieval provenance is incomplete: {definition['id']}")
        relative = Path(definition["path"])
        if definition["id"].startswith("natural_earth_"):
            if relative.parent != NATURAL_EARTH_PROFILE_DIR or relative.suffix.lower() != ".zip":
                raise SystemExit(
                    f"Natural Earth archive must be available under "
                    f"{NATURAL_EARTH_PROFILE_DIR}: {relative}"
                )
            expected_profile_archives.add(relative.name)
        file_path = (root / relative).resolve(strict=True)
        if not file_path.is_relative_to(root) or not file_path.is_file():
            raise SystemExit(f"Auxiliary file is missing or outside its directory: {relative}")
        if file_path.stat().st_size != record.get("size_bytes") or sha256(file_path) != record.get("sha256"):
            raise SystemExit(f"Auxiliary file failed size/SHA-256 verification: {relative}")
        if definition["id"].startswith("natural_earth_") and not zipfile.is_zipfile(file_path):
            raise SystemExit(f"Natural Earth profile input is not a ZIP archive: {relative}")
    if len(natural_earth_sources) != 22:
        raise SystemExit(f"Expected 22 Natural Earth profile archives, got {len(natural_earth_sources)}")
    profile_archive_dir = root / NATURAL_EARTH_PROFILE_DIR
    actual_profile_archives = {
        path.name for path in profile_archive_dir.iterdir() if path.is_file() and path.suffix.lower() == ".zip"
    }
    if actual_profile_archives != expected_profile_archives:
        missing = sorted(expected_profile_archives - actual_profile_archives)
        unexpected = sorted(actual_profile_archives - expected_profile_archives)
        raise SystemExit(
            f"Natural Earth profile archive set mismatch; missing={missing}, unexpected={unexpected}"
        )
    extracted = manifest.get("natural_earth_extracted_files")
    if not isinstance(extracted, list) or not extracted:
        raise SystemExit("Natural Earth extracted-file provenance is missing")
    shapefiles = 0
    for record in extracted:
        relative = Path(record.get("path", ""))
        file_path = (root / relative).resolve(strict=True)
        if not file_path.is_relative_to(root) or not file_path.is_file():
            raise SystemExit(f"Extracted Natural Earth file is missing or outside its directory: {relative}")
        if file_path.stat().st_size != record.get("size_bytes") or sha256(file_path) != record.get("sha256"):
            raise SystemExit(f"Extracted Natural Earth file failed verification: {relative}")
        shapefiles += file_path.suffix.lower() == ".shp"
    if shapefiles != sum(item["id"].startswith("natural_earth_") for item in expected):
        raise SystemExit("Natural Earth extracted shapefile set is incomplete")
    print(f"Verified {len(records)} auxiliary input files and provenance records in {root}")


if __name__ == "__main__":
    main()
