#!/usr/bin/env python3
"""Download the pinned profile's declared auxiliary files into persistent storage."""
import argparse
import hashlib
import json
import os
import shutil
import tempfile
import zipfile
from pathlib import PurePosixPath
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_IMAGE = (
    "docker.io/openmaptiles/planetiler-openmaptiles@sha256:"
    "a5d93e943f193ec0b0e5a93f45d01854caee1a0dc2c26124028a9665cd6ea8ec"
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_dir", type=Path, help="Persistent auxiliary data directory; must not exist")
    parser.add_argument("--planetiler-image", default=DEFAULT_IMAGE)
    parser.add_argument("--source-list", type=Path, default=SCRIPT_DIR / "auxiliary-sources.json")
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit(f"Refusing to overwrite existing auxiliary directory: {args.output_dir}")

    definitions = json.loads(args.source_list.read_text())["sources"]
    args.output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{args.output_dir.name}.", dir=args.output_dir.parent))
    try:
        records = []
        extracted_natural_earth = staging / "natural_earth"
        extracted_natural_earth.mkdir()
        for definition in definitions:
            relative = Path(definition["path"])
            if relative.is_absolute() or ".." in relative.parts:
                raise SystemExit(f"Unsafe auxiliary path: {relative}")
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_name(target.name + ".part")
            request = Request(definition["url"], headers={"User-Agent": "geology-map-data OSM pipeline"})
            with urlopen(request, timeout=120) as response, partial.open("wb") as output:
                shutil.copyfileobj(response, output)
                last_modified = response.headers.get("Last-Modified")
                etag = response.headers.get("ETag")
            if not partial.is_file() or partial.stat().st_size == 0:
                raise SystemExit(f"Downloaded auxiliary file is empty: {definition['id']}")
            source_format = definition.get("format", "zip")
            if source_format == "zip":
                if not zipfile.is_zipfile(partial):
                    raise SystemExit(f"Downloaded auxiliary file is not a ZIP archive: {definition['id']}")
                with zipfile.ZipFile(partial) as archive:
                    invalid_member = archive.testzip()
                    if invalid_member is not None:
                        raise SystemExit(f"Corrupt ZIP member in {definition['id']}: {invalid_member}")
                    if definition["id"].startswith("natural_earth_"):
                        for member in archive.infolist():
                            member_path = PurePosixPath(member.filename)
                            if member_path.is_absolute() or ".." in member_path.parts:
                                raise SystemExit(f"Unsafe path in Natural Earth archive: {member.filename}")
                            if (member.external_attr >> 16) & 0o170000 == 0o120000:
                                raise SystemExit(f"Symbolic link in Natural Earth archive: {member.filename}")
                            if member.is_dir():
                                continue
                            extracted = extracted_natural_earth / Path(*member_path.parts)
                            if extracted.exists():
                                raise SystemExit(f"Duplicate Natural Earth member path: {member.filename}")
                            extracted.parent.mkdir(parents=True, exist_ok=True)
                            with archive.open(member) as source, extracted.open("wb") as extracted_output:
                                shutil.copyfileobj(source, extracted_output)
            elif source_format == "parquet":
                if partial.stat().st_size < 8:
                    raise SystemExit(f"Downloaded Parquet file is truncated: {definition['id']}")
                with partial.open("rb") as data:
                    data.seek(-4, os.SEEK_END)
                    if data.read(4) != b"PAR1":
                        raise SystemExit(f"Downloaded auxiliary file is not a Parquet file: {definition['id']}")
                    data.seek(0)
                    if data.read(4) != b"PAR1":
                        raise SystemExit(f"Downloaded auxiliary file is not a Parquet file: {definition['id']}")
            else:
                raise SystemExit(f"Unsupported auxiliary format: {definition['format']}")
            partial.rename(target)
            records.append({
                **definition,
                "format": source_format,
                "retrieved_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "last_modified": last_modified,
                "etag": etag,
                "size_bytes": target.stat().st_size,
                "sha256": sha256(target),
            })

        extracted_files = [
            {"path": path.relative_to(staging).as_posix(), "size_bytes": path.stat().st_size, "sha256": sha256(path)}
            for path in sorted(extracted_natural_earth.rglob("*")) if path.is_file()
        ]
        shapefile_count = sum(Path(item["path"]).suffix.lower() == ".shp" for item in extracted_files)
        if shapefile_count != sum(record["id"].startswith("natural_earth_") for record in records):
            raise SystemExit("Natural Earth archives did not produce the expected shapefile set")
        manifest = {
            "created_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "planetiler_image": args.planetiler_image,
            "profile_revision": "unknown; pinned image digest identifies the executable, not its source commit",
            "profile_schema_version": "unknown; verify against the pinned image before production",
            "sources": records,
            "natural_earth_extracted_files": extracted_files,
        }
        (staging / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        os.rename(staging, args.output_dir)
    except BaseException:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    print(f"Prepared {len(records)} auxiliary files in {args.output_dir}")


if __name__ == "__main__":
    main()
