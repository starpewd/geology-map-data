# Project Liberty style variant (16 OpenMapTiles layers)

This directory maintains the project's cartographic variant of the MapLibre Liberty
style. It extends upstream OpenFreeMap Liberty (commit `006ea5796803ba2df4330888836cb0a8f17473b4`)
to utilize all 16 vector layers present in OpenMapTiles 3.16.0 extracts, specifically adding
support for `mountain_peak` and `housenumber`.

## Objectives and constraints

1. **Complete layer coverage:** Upstream Liberty styles render 14 of the 16 OpenMapTiles
   layers. OpenMapTiles 3.16.0 extracts include `mountain_peak` and `housenumber`, which are
   now explicitly rendered.
2. **Preservation of upstream cartography:** All original 111 layers from upstream commit
   `006ea5796803ba2df4330888836cb0a8f17473b4` remain unmodified in their filters, layout,
   paint definitions, and relative display order.
3. **Dual online/offline target:** The identical layer stack serves both the online OpenFreeMap
   endpoint (`https://tiles.openfreemap.org/planet`) and local offline PMTiles archives
   (`pmtiles://file:///...`). Only source and asset URIs differ.
4. **Utility for geological field work:** Natural orographic summits, spot heights, limestone
   cliffs, canyon walls, ridges, and saddles are rendered with hypsometric elevations in meters,
   providing vital orientation in mountainous and karst terrain.

## Layer additions

The variant adds 7 specialized layers, expanding the total layer count from 111 to 118:

| Layer ID | Type | Source-layer | Minzoom | Description & Cartographic Styling |
| --- | --- | --- | --- | --- |
| `cliff` | `line` | `mountain_peak` | 12.5 | Rocky precipices, quarry faces, and karst canyon rims. Solid umber line (`#52463e`), 0.8–3.6 px width. Inserted before infrastructure casings. |
| `ridge` | `line` | `mountain_peak` | 12.0 | Orographic divide lines and sharp crests (`ridge` and `arete`). Dashed line (`#736357` / `#4a3b32`, `dasharray: [3, 2]`), 0.7–2.0 px width. |
| `mountain_peak_line_label` | `symbol` | `mountain_peak` | 13.5 | Names along cliffs, rock walls, and ridges (e.g. Býčí skála, Machatova skála). Line-placement italic label (`#52463e`, `Noto Sans Italic`). |
| `housenumber` | `symbol` | `housenumber` | 17.0 | Building address numbers. Unobtrusive neutral grey (`#777777`, 8.5–10.5 px, `Noto Sans Regular`). `symbol-sort-key: 1000`, `text-allow-overlap: false`, `text-optional: true` prevents collision with street names or POIs. |
| `volcano` | `symbol` | `mountain_peak` | 8.0 | Volcanic peaks and cones. Distinctive crimson-brown (`#7a1c1c`, `Noto Sans Bold`), icon `volcano_11`. Sorted by `rank`. |
| `mountain_peak` | `symbol` | `mountain_peak` | 8.0 | Mountain peaks, hills, and spot heights (`kótované body`). Warm dark brown (`#523d2e`, `Noto Sans Regular`), icon `mountain_11`. Sorted by `rank`. Shows `{name}\n{ele} m`, or `{ele} m` when unnamed. |
| `mountain_saddle` | `symbol` | `mountain_peak` | 10.0 | Mountain passes, cols, and saddles. Muted brown (`#5c4a3d`, `Noto Sans Italic`), icon `dot_9`. Shows `{name}\n{ele} m`. |

## Files

- `style.json`: Canonical style definition using OpenFreeMap standard domain macros (`__TILEJSON_DOMAIN__`, `__SPRITE_DOMAIN__`, `__GLYPH_DOMAIN__`).
- `style-online.json`: Direct runtime style pointing to live `tiles.openfreemap.org` endpoints.
- `style.template.json`: Offline package template containing MapLibre Native substitution placeholders:
  - `{{PMTILES_ARCHIVE_URI}}`: target local PMTiles (e.g. `pmtiles://file:///.../czechia.pmtiles`)
  - `{{SPRITE_FILE_URI}}`: base URI to local sprite assets (without file extensions)
  - `{{GLYPH_PBF_URI_TEMPLATE}}`: local glyph PBF path pattern (`file:///.../fonts/{fontstack}/{range}.pbf`)
  - `{{NATURAL_EARTH_TILE_URI_TEMPLATE}}`: local shaded relief raster XYZ tiles

## Verification and testing

Regression tests in `tests/test_liberty_style.py` verify:
- All 16 OpenMapTiles source layers are represented.
- All original 111 layers match upstream commit `006ea5796803ba2df4330888836cb0a8f17473b4`.
- Elevation attribute `ele` displays meters (`" m"`).
- House numbers display only from zoom 17+.
- Only bundled font stacks (`Noto Sans Regular`, `Noto Sans Italic`, `Noto Sans Bold`) and existing sprite icons are referenced.
- Online and offline template layer arrays are identical.
