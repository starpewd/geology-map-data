"""Regression tests for the project Liberty style variant (16 OpenMapTiles layers)."""
import json
import unittest
from pathlib import Path

DATA_REPO = Path(__file__).resolve().parents[1]
STYLES_DIR = DATA_REPO / "styles/liberty"
UPSTREAM_COMMIT = "006ea5796803ba2df4330888836cb0a8f17473b4"

# Optional path to upstream checkout if available in environment
UPSTREAM_STYLE_PATH = Path("/tmp/geology-map-osm-e2e-czechia/openfreemap-styles-src/styles/liberty/style.json")

EXPECTED_16_SOURCE_LAYERS = {
    "aerodrome_label",
    "aeroway",
    "boundary",
    "building",
    "housenumber",
    "landcover",
    "landuse",
    "mountain_peak",
    "park",
    "place",
    "poi",
    "transportation",
    "transportation_name",
    "water",
    "water_name",
    "waterway",
}

SUPPORTED_FONT_STACKS = {
    ("Noto Sans Regular",),
    ("Noto Sans Italic",),
    ("Noto Sans Bold",),
}

NEW_LAYER_IDS = {
    "cliff",
    "ridge",
    "mountain_peak_line_label",
    "housenumber",
    "volcano",
    "mountain_peak",
    "mountain_saddle",
}


class LibertyStyleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.style_canonical_path = STYLES_DIR / "style.json"
        cls.style_online_path = STYLES_DIR / "style-online.json"
        cls.style_template_path = STYLES_DIR / "style.template.json"

        with cls.style_canonical_path.open("r", encoding="utf-8") as f:
            cls.style_canonical = json.load(f)
        with cls.style_online_path.open("r", encoding="utf-8") as f:
            cls.style_online = json.load(f)
        with cls.style_template_path.open("r", encoding="utf-8") as f:
            cls.style_template = json.load(f)

    def test_style_files_exist_and_are_valid_json(self) -> None:
        self.assertTrue(self.style_canonical_path.is_file())
        self.assertTrue(self.style_online_path.is_file())
        self.assertTrue(self.style_template_path.is_file())
        self.assertEqual(self.style_canonical.get("version"), 8)
        self.assertEqual(self.style_online.get("version"), 8)
        self.assertEqual(self.style_template.get("version"), 8)

    def test_layer_counts_and_consistency(self) -> None:
        layers_canonical = self.style_canonical.get("layers", [])
        layers_online = self.style_online.get("layers", [])
        layers_template = self.style_template.get("layers", [])

        # Total 111 original + 7 new = 118 layers
        self.assertEqual(len(layers_canonical), 118)
        self.assertEqual(len(layers_online), 118)
        self.assertEqual(len(layers_template), 118)

        # Layers across all three files must be completely identical
        self.assertEqual(layers_canonical, layers_online)
        self.assertEqual(layers_canonical, layers_template)

    def test_all_16_openmaptiles_source_layers_are_present(self) -> None:
        source_layers = {
            layer["source-layer"]
            for layer in self.style_canonical["layers"]
            if "source-layer" in layer
        }
        self.assertEqual(len(source_layers), 16)
        self.assertEqual(source_layers, EXPECTED_16_SOURCE_LAYERS)
        self.assertIn("mountain_peak", source_layers)
        self.assertIn("housenumber", source_layers)

    def test_preserves_original_111_layers_when_upstream_available(self) -> None:
        if not UPSTREAM_STYLE_PATH.is_file():
            self.skipTest("Upstream style source file not available for diff comparison")

        with UPSTREAM_STYLE_PATH.open("r", encoding="utf-8") as f:
            upstream = json.load(f)

        orig_layers = upstream.get("layers", [])
        self.assertEqual(len(orig_layers), 111)

        # Filter out our new 7 layers from the project style:
        filtered_project_layers = [
            l for l in self.style_canonical["layers"]
            if l["id"] not in NEW_LAYER_IDS
        ]
        self.assertEqual(len(filtered_project_layers), 111)
        self.assertEqual(filtered_project_layers, orig_layers)

    def test_mountain_peak_rules(self) -> None:
        by_id = {l["id"]: l for l in self.style_canonical["layers"]}

        # 1. cliff (line layer)
        cliff = by_id.get("cliff")
        self.assertIsNotNone(cliff)
        self.assertEqual(cliff["type"], "line")
        self.assertEqual(cliff["source-layer"], "mountain_peak")
        self.assertGreaterEqual(cliff.get("minzoom", 0), 12)
        self.assertEqual(cliff["paint"]["line-color"], "#52463e")

        # 2. ridge (line layer)
        ridge = by_id.get("ridge")
        self.assertIsNotNone(ridge)
        self.assertEqual(ridge["type"], "line")
        self.assertEqual(ridge["source-layer"], "mountain_peak")
        self.assertIn("line-dasharray", ridge.get("paint", {}))

        # 3. cliff/ridge line labels
        cliff_label = by_id.get("mountain_peak_line_label")
        self.assertIsNotNone(cliff_label)
        self.assertEqual(cliff_label["type"], "symbol")
        self.assertEqual(cliff_label["layout"]["symbol-placement"], "line")
        self.assertEqual(cliff_label["layout"]["text-font"], ["Noto Sans Italic"])

        # 4. volcano (point symbol)
        volcano = by_id.get("volcano")
        self.assertIsNotNone(volcano)
        self.assertEqual(volcano["type"], "symbol")
        self.assertEqual(volcano["layout"]["icon-image"], "volcano_11")
        self.assertEqual(volcano["paint"]["text-color"], "#7a1c1c")
        self.assertEqual(volcano["layout"]["symbol-sort-key"], ["to-number", ["get", "rank"]])

        # 5. mountain_peak (point symbol)
        peak = by_id.get("mountain_peak")
        self.assertIsNotNone(peak)
        self.assertEqual(peak["type"], "symbol")
        self.assertEqual(peak["layout"]["icon-image"], "mountain_11")
        self.assertEqual(peak["paint"]["text-color"], "#523d2e")
        self.assertEqual(peak["layout"]["symbol-sort-key"], ["to-number", ["get", "rank"]])
        self.assertTrue(peak["layout"]["text-optional"])

        # 6. mountain_saddle (point symbol)
        saddle = by_id.get("mountain_saddle")
        self.assertIsNotNone(saddle)
        self.assertEqual(saddle["type"], "symbol")
        self.assertEqual(saddle["layout"]["icon-image"], "dot_9")
        self.assertEqual(saddle["layout"]["text-font"], ["Noto Sans Italic"])

        # Elevation display in text-field expression
        for layer in (volcano, peak, saddle):
            text_field = layer["layout"]["text-field"]
            self.assertEqual(text_field[0], "case")
            # Verify elevation suffix " m" is present in expression
            expr_str = json.dumps(text_field)
            self.assertIn('" m"', expr_str)
            self.assertIn('"ele"', expr_str)

    def test_housenumber_rules(self) -> None:
        by_id = {l["id"]: l for l in self.style_canonical["layers"]}
        hn = by_id.get("housenumber")
        self.assertIsNotNone(hn)
        self.assertEqual(hn["type"], "symbol")
        self.assertEqual(hn["source-layer"], "housenumber")
        self.assertEqual(hn.get("minzoom"), 17, "House numbers must display only at zoom 17+")
        self.assertEqual(hn["layout"]["text-field"], ["get", "housenumber"])
        self.assertFalse(hn["layout"]["text-allow-overlap"])
        self.assertTrue(hn["layout"]["text-optional"])
        self.assertEqual(hn["layout"]["symbol-sort-key"], 1000, "House numbers must have lowest placement priority")
        self.assertEqual(hn["paint"]["text-color"], "#777777", "House numbers must use subtle subdued grey")

    def test_supported_font_stacks(self) -> None:
        for layer in self.style_canonical["layers"]:
            layout = layer.get("layout", {})
            tf = layout.get("text-font")
            if tf is not None and isinstance(tf, list):
                self.assertIn(
                    tuple(tf),
                    SUPPORTED_FONT_STACKS,
                    f"Layer {layer['id']} uses unsupported font stack: {tf}",
                )

    def test_dual_target_sources_configuration(self) -> None:
        # Online configuration
        online_sources = self.style_online["sources"]
        self.assertEqual(online_sources["openmaptiles"]["url"], "https://tiles.openfreemap.org/planet")
        self.assertEqual(self.style_online["sprite"], "https://tiles.openfreemap.org/sprites/liberty")
        self.assertEqual(self.style_online["glyphs"], "https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf")

        # Offline template configuration
        template_sources = self.style_template["sources"]
        self.assertEqual(template_sources["openmaptiles"]["url"], "{{PMTILES_ARCHIVE_URI}}")
        self.assertEqual(self.style_template["sprite"], "{{SPRITE_FILE_URI}}")
        self.assertEqual(self.style_template["glyphs"], "{{GLYPH_PBF_URI_TEMPLATE}}")
        self.assertEqual(template_sources["ne2_shaded"]["tiles"], ["{{NATURAL_EARTH_TILE_URI_TEMPLATE}}"])


if __name__ == "__main__":
    unittest.main()
