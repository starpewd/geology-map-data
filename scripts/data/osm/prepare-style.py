#!/usr/bin/env python3
"""Package an explicitly non-loadable MapLibre Native style template."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from urllib.parse import urlparse

PMTILES = "{{PMTILES_ARCHIVE_URI}}"
SPRITE = "{{SPRITE_FILE_URI}}"
GLYPHS = "{{GLYPH_PBF_URI_TEMPLATE}}"
FONT_RELEASE_URL = "https://github.com/openmaptiles/fonts/releases/download/v2.0/noto-open-sans.zip"


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def directory_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
        digest.update(b"\0")
    return digest.hexdigest()


def git_provenance(repository: Path) -> dict[str, object]:
    commit = subprocess.check_output(
        ["git", "-C", str(repository), "rev-parse", "HEAD"], text=True
    ).strip()
    changes = subprocess.check_output(
        ["git", "-C", str(repository), "status", "--porcelain"], text=True
    ).splitlines()
    return {"repository": str(repository), "commit": commit, "working_tree_changes": changes}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("style_dir", type=Path, help="Generated OpenMapTiles build/style directory")
    parser.add_argument("fonts_dir", type=Path, help="OpenMapTiles data/fonts directory")
    parser.add_argument("output_dir", type=Path, help="New output directory; must not exist")
    parser.add_argument("--license-file", type=Path, required=True, help="OpenMapTiles license notice to include")
    parser.add_argument("--source-repository", type=Path, help="OpenMapTiles Git checkout (defaults to build/style ancestor)")
    parser.add_argument("--font-package-release", default="v2.0", help="OpenMapTiles fonts release referenced by its Makefile; verify before production")
    parser.add_argument("--font-archive-sha256", default="unknown", help="Official downloaded archive SHA-256, if available")
    parser.add_argument("--archive-name", default="czechia.pmtiles", help="Dataset PMTiles filename for runtime documentation")
    args = parser.parse_args()
    if args.output_dir.exists():
        raise SystemExit(f"Refusing to overwrite existing directory: {args.output_dir}")

    style_dir = args.style_dir.resolve(strict=True)
    fonts_dir = args.fonts_dir.resolve(strict=True)
    license_file = args.license_file.resolve(strict=True)
    source_repo = args.source_repository.resolve(strict=True) if args.source_repository else style_dir.parents[1]
    if args.font_archive_sha256 != "unknown" and (
        len(args.font_archive_sha256) != 64
        or any(character not in "0123456789abcdefABCDEF" for character in args.font_archive_sha256)
    ):
        raise SystemExit("--font-archive-sha256 must be a 64-character hexadecimal SHA-256 or 'unknown'")
    style_path = style_dir / "style.json"
    style = json.loads(style_path.read_text())
    if not isinstance(style.get("sources"), dict) or "openmaptiles" not in style["sources"]:
        raise SystemExit("Expected an OpenMapTiles source in style.json")
    source = style["sources"]["openmaptiles"]
    if source.get("type") != "vector":
        raise SystemExit("OpenMapTiles source is not vector data")
    source.pop("tiles", None)
    source["url"] = PMTILES
    style["sprite"] = SPRITE
    style["glyphs"] = GLYPHS

    args.output_dir.mkdir(parents=True)
    try:
        template_path = args.output_dir / "style.template.json"
        template_path.write_text(json.dumps(style, indent=2) + "\n")
        for name in ("sprite.json", "sprite.png", "sprite@2x.json", "sprite@2x.png"):
            shutil.copy2(style_dir / name, args.output_dir / name)
        shutil.copytree(fonts_dir, args.output_dir / "fonts")
        shutil.copy2(license_file, args.output_dir / "OPENMAPTILES-LICENSE.md")

        font_notices = []
        for source_notice in sorted(
            p for p in fonts_dir.rglob("*")
            if p.is_file() and p.name.lower().startswith(("license", "ofl", "copyright"))
        ):
            notice_target = args.output_dir / "licenses" / "fonts" / source_notice.relative_to(fonts_dir)
            notice_target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_notice, notice_target)
            font_notices.append(notice_target.relative_to(args.output_dir).as_posix())

        attribution = (
            "# Map data and style attribution\n\n"
            "© OpenStreetMap contributors — https://www.openstreetmap.org/copyright\n\n"
            "© OpenMapTiles — https://openmaptiles.org/\n\n"
            "The OSM-derived dataset is subject to ODbL 1.0. OpenMapTiles code/schema "
            "and cartographic design terms are described in `OPENMAPTILES-LICENSE.md`.\n"
        )
        (args.output_dir / "ATTRIBUTION.md").write_text(attribution)

        placeholders = {"PMTILES_ARCHIVE_URI": PMTILES, "SPRITE_FILE_URI": SPRITE, "GLYPH_PBF_URI_TEMPLATE": GLYPHS}
        expected_values = {"pmtiles": PMTILES, "sprite": SPRITE, "glyphs": GLYPHS}
        actual_values = {
            "pmtiles": style["sources"]["openmaptiles"].get("url"),
            "sprite": style.get("sprite"),
            "glyphs": style.get("glyphs"),
        }
        if actual_values != expected_values:
            raise SystemExit("Template resource placeholders are inconsistent")
        if any(urlparse(value).scheme in {"http", "https"} for value in actual_values.values()):
            raise SystemExit("Template contains an external style resource URL")
        for src in style["sources"].values():
            for field in ("url", "tiles", "data"):
                values = src.get(field, []) if isinstance(src.get(field), list) else [src.get(field)]
                for value in values:
                    if isinstance(value, str) and urlparse(value).scheme in {"http", "https"}:
                        raise SystemExit(f"External style source reference remains: {value}")

        style_git = git_provenance(source_repo)
        manifest = {
            "loadable_runtime_style": False,
            "style_template_file": template_path.name,
            "style_template_sha256": file_hash(template_path),
            "sprite_file_sha256": {
                name: file_hash(args.output_dir / name)
                for name in ("sprite.json", "sprite.png", "sprite@2x.json", "sprite@2x.png")
            },
            "placeholders": placeholders,
            "runtime_requirements": {
                "style_json": "Pass the absolute filesystem path to style.template.json as the MapLibre style string after substitutions.",
                "substitutions": {
                    "PMTILES_ARCHIVE_URI": "pmtiles://file:///absolute/path/to/" + args.archive_name,
                    "SPRITE_FILE_URI": "file:///absolute/path/to/style/sprite",
                    "GLYPH_PBF_URI_TEMPLATE": "file:///absolute/path/to/style/fonts/{fontstack}/{range}.pbf",
                },
                "sprite_note": "Sprite URI is the base path; native renderer adds sprite scale and file extensions.",
                "offline": "All substituted paths must resolve inside the installed dataset; do not use asset:// or relative paths for Native resources.",
            },
            "style_source": {
                **style_git,
                "style_json_sha256": file_hash(style_path),
            },
            "font_package": {
                "release": args.font_package_release,
                "release_url": FONT_RELEASE_URL,
                "archive_sha256": args.font_archive_sha256,
                "packaged_tree_sha256": directory_hash(fonts_dir),
                "checksum_note": "packaged_tree_sha256 hashes sorted relative paths and file bytes; it is not the source ZIP checksum",
            },
            "licenses_and_notices": {
                "included_files": ["OPENMAPTILES-LICENSE.md", "ATTRIBUTION.md", *font_notices],
                "included_file_sha256": {
                    name: file_hash(args.output_dir / name)
                    for name in ["OPENMAPTILES-LICENSE.md", "ATTRIBUTION.md", *font_notices]
                },
                "included_style_attribution": "© OpenStreetMap contributors; © OpenMapTiles",
                "font_notices_included": bool(font_notices),
                "font_notice_limitation": None if font_notices else "No font license notice was present in the supplied glyph directory; obtain and include the verified font package notices before distribution.",
                "auxiliary_data_licenses": "Recorded with auxiliary-input provenance and must be reviewed for the dataset distribution package.",
            },
        }
        (args.output_dir / "style-template-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    except BaseException:
        shutil.rmtree(args.output_dir)
        raise


if __name__ == "__main__":
    main()
