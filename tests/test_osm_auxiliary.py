import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[1]
VERIFY_SCRIPT = REPOSITORY / "scripts/data/osm/verify-auxiliary.py"
GENERATE_SCRIPT = REPOSITORY / "scripts/data/osm/generate-mbtiles.sh"
IMAGE = "planetiler-image@sha256:abc"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AuxiliaryLayoutTest(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.temp_path = Path(temp.name)
        self.root = self.temp_path / "auxiliary"
        self.root.mkdir()
        self.sources = []
        self.manifest_sources = []
        self.extracted_files = []

        archive_dir = self.root / "source-archives/natural_earth"
        archive_dir.mkdir(parents=True)
        extracted_dir = self.root / "natural_earth"
        extracted_dir.mkdir()
        for index in range(22):
            name = f"ne_test_{index}.zip"
            archive_path = archive_dir / name
            with zipfile.ZipFile(archive_path, "w") as archive:
                archive.writestr(f"ne_test_{index}.shp", b"shapefile fixture")
            definition = {
                "id": f"natural_earth_test_{index}",
                "path": f"source-archives/natural_earth/{name}",
                "url": f"https://example.invalid/{name}",
                "revision": None,
                "revision_note": "fixture",
                "format": "zip",
            }
            self.sources.append(definition)
            self.manifest_sources.append(
                {
                    **definition,
                    "retrieved_at_utc": "2026-01-01T00:00:00Z",
                    "size_bytes": archive_path.stat().st_size,
                    "sha256": sha256(archive_path),
                }
            )

            extracted = extracted_dir / f"ne_test_{index}.shp"
            extracted.write_bytes(b"extracted shape fixture")
            self.extracted_files.append(
                {
                    "path": f"natural_earth/{extracted.name}",
                    "size_bytes": extracted.stat().st_size,
                    "sha256": sha256(extracted),
                }
            )

        self.source_list = self.temp_path / "sources.json"
        self.source_list.write_text(json.dumps({"sources": self.sources}))
        self.manifest_path = self.root / "manifest.json"
        self.manifest = {
            "planetiler_image": IMAGE,
            "sources": self.manifest_sources,
            "natural_earth_extracted_files": self.extracted_files,
        }
        self.write_manifest()

    def write_manifest(self) -> None:
        self.manifest_path.write_text(json.dumps(self.manifest))

    def verify(self) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(VERIFY_SCRIPT),
                str(self.root),
                IMAGE,
                "--source-list",
                str(self.source_list),
            ],
            capture_output=True,
            text=True,
            check=False,
        )

    def test_verifies_all_archives_at_the_profile_path(self) -> None:
        result = self.verify()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Verified 22 auxiliary input files", result.stdout)

    def test_rejects_archives_moved_into_extracted_directory(self) -> None:
        source = self.sources[0]
        record = self.manifest_sources[0]
        archive = self.root / source["path"]
        misplaced_path = "natural_earth/ne_test_0.zip"
        misplaced = self.root / misplaced_path
        misplaced.write_bytes(archive.read_bytes())
        source["path"] = misplaced_path
        record["path"] = misplaced_path
        record["size_bytes"] = misplaced.stat().st_size
        record["sha256"] = sha256(misplaced)
        self.source_list.write_text(json.dumps({"sources": self.sources}))
        self.write_manifest()

        result = self.verify()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Natural Earth archive must be available", result.stderr)

    def test_generator_passes_the_profile_archive_directory(self) -> None:
        content = GENERATE_SCRIPT.read_text()
        self.assertIn("--natural_earth_path=/aux/source-archives/natural_earth", content)
        self.assertNotIn("--natural_earth_path=/aux/natural_earth \\", content)


if __name__ == "__main__":
    unittest.main()
