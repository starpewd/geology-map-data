#!/usr/bin/env python3
"""Validate map_catalog.json and every locally available catalogue file."""

import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "map_catalog.json"
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
VERSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,127}$")
SHA_PATTERN = re.compile(r"^[a-fA-F0-9]{64}$")


def fail(message: str) -> None:
    raise SystemExit(f"Catalog validation failed: {message}")


def validate() -> None:
    try:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        fail(str(error))
    if (
        not isinstance(catalog, dict)
        or type(catalog.get("schemaVersion")) is not int
        or catalog["schemaVersion"] != 2
    ):
        fail("schemaVersion must be 2")
    datasets = catalog.get("datasets")
    if not isinstance(datasets, list):
        fail("datasets must be an array")

    identifiers: set[str] = set()
    for dataset in datasets:
        if not isinstance(dataset, dict):
            fail("each dataset must be an object")
        identifier = dataset.get("id")
        if not isinstance(identifier, str) or not ID_PATTERN.fullmatch(identifier):
            fail(f"invalid dataset id: {identifier!r}")
        if identifier in identifiers:
            fail(f"duplicate dataset id: {identifier}")
        identifiers.add(identifier)
        for field in ("name", "description", "kind", "source", "license"):
            if not isinstance(dataset.get(field), str) or not dataset[field].strip():
                fail(f"{identifier}: {field} is required")

        available = dataset.get("available")
        version = dataset.get("version")
        files = dataset.get("files")
        size = dataset.get("sizeBytes")
        if not isinstance(available, bool) or not isinstance(files, list):
            fail(f"{identifier}: available and files have invalid types")
        if type(size) is not int or size < 0:
            fail(f"{identifier}: sizeBytes must be a nonnegative integer")
        if available:
            if not isinstance(version, str) or not VERSION_PATTERN.fullmatch(version):
                fail(f"{identifier}: available datasets require a valid version identifier")
            if not files:
                fail(f"{identifier}: available datasets require files")
        elif version != "" or files or size != 0:
            fail(f"{identifier}: unavailable datasets require empty version/files and size 0")

        file_names: set[str] = set()
        declared_total = 0
        for item in files:
            if not isinstance(item, dict):
                fail(f"{identifier}: each file must be an object")
            name = item.get("name")
            if not isinstance(name, str):
                fail(f"{identifier}: file name is required")
            relative = PurePosixPath(name)
            if (
                relative.is_absolute()
                or re.match(r"^[A-Za-z]:", name)
                or any(part in ("", ".", "..") for part in name.split("/"))
                or "\\" in name
                or "\x00" in name
                or name == "installation.json"
                or name.startswith("installation.json/")
            ):
                fail(f"{identifier}: unsafe file path {name!r}")
            if name in file_names:
                fail(f"{identifier}: duplicate file path {name!r}")
            if any(name.startswith(f"{existing}/") or existing.startswith(f"{name}/") for existing in file_names):
                fail(f"{identifier}: conflicting file paths at {name!r}")
            file_names.add(name)
            file_size = item.get("sizeBytes")
            digest = item.get("sha256")
            url = item.get("url")
            try:
                parsed_url = urlparse(url) if isinstance(url, str) else None
                hostname = parsed_url.hostname if parsed_url is not None else None
                if parsed_url is not None:
                    parsed_url.port
            except ValueError:
                fail(f"{identifier}/{name}: invalid HTTPS URL")
            if type(file_size) is not int or file_size <= 0:
                fail(f"{identifier}/{name}: sizeBytes must be positive")
            if not isinstance(digest, str) or not SHA_PATTERN.fullmatch(digest):
                fail(f"{identifier}/{name}: invalid SHA-256")
            if (
                parsed_url is None
                or parsed_url.scheme != "https"
                or not hostname
                or parsed_url.username
                or parsed_url.password
                or parsed_url.fragment
            ):
                fail(f"{identifier}/{name}: invalid HTTPS URL")
            declared_total += file_size

            # Repository-hosted raw assets are checked against their local source.
            marker = "/geology-map-data/"
            if hostname == "raw.githubusercontent.com" and marker in parsed_url.path:
                asset_path = parsed_url.path.split(marker, 1)[1]
                asset_parts = asset_path.split("/")
                if asset_parts and (
                    asset_parts[0] in ("main", "master")
                    or re.fullmatch(r"[a-fA-F0-9]{40}", asset_parts[0])
                ):
                    asset_parts = asset_parts[1:]
                local_file = ROOT.joinpath(*asset_parts).resolve()
                if not local_file.is_relative_to(ROOT.resolve()):
                    fail(f"{identifier}/{name}: local asset path escapes repository root")
                try:
                    actual_size = local_file.stat().st_size
                    actual_hash = hashlib.sha256(local_file.read_bytes()).hexdigest()
                except OSError as error:
                    fail(f"{identifier}/{name}: cannot read {local_file}: {error}")
                if actual_size != file_size or actual_hash.lower() != digest.lower():
                    fail(f"{identifier}/{name}: local size or SHA-256 does not match catalog")
        if size != declared_total:
            fail(f"{identifier}: sizeBytes must equal the sum of file sizes")

        compatibility = dataset.get("compatibility", {})
        metadata = dataset.get("metadata", {})
        if not isinstance(compatibility, dict) or not isinstance(metadata, dict):
            fail(f"{identifier}: compatibility and metadata must be objects")
        stable_version = re.compile(r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
        bounds = {}
        for field in ("appMinVersion", "appMaxVersion"):
            value = compatibility.get(field)
            if value is not None:
                if not isinstance(value, str) or not stable_version.fullmatch(value):
                    fail(f"{identifier}: compatibility.{field} must be stable major.minor.patch")
                bounds[field] = tuple(int(part) for part in value.split("."))
        if (
            "appMinVersion" in bounds
            and "appMaxVersion" in bounds
            and bounds["appMinVersion"] > bounds["appMaxVersion"]
        ):
            fail(f"{identifier}: appMinVersion exceeds appMaxVersion")

    print(f"Validated {len(datasets)} datasets in {CATALOG.name}.")


if __name__ == "__main__":
    validate()
