# Offline Liberty / MapLibre handoff

## Repository
- Branch: feature/osm-e2e-czechia
- Previous commit: 62f1efe
- Production app: separate repository ~/develop/geology-map
- This repository contains styles, scripts, documentation and tests.
- It does NOT contain the complete PMTiles archive or probe asset bundle.

## Goal
Build an offline OpenFreeMap Liberty basemap for the Flutter Android
app geology-map, using local PMTiles, glyphs, sprite and Natural Earth
raster relief.

## Probe status
The disposable Flutter probe was located at /tmp/liberty_offline_probe.
That directory has disappeared. Its main.dart was preserved in the
previous ChatGPT conversation, but the asset bundle was not preserved.

The emulator is currently unavailable.

The probe used maplibre_gl 0.27.1, matching the production app.

## Confirmed findings
- Production geology-map renders online Liberty labels correctly.
- Probe rendered map geometry, a green circle and a magenta background.
- Text labels did not render in the probe.
- All 28 text symbol layers in the Liberty style explicitly use:
  - Noto Sans Regular: 12 layers
  - Noto Sans Italic: 11 layers
  - Noto Sans Bold: 5 layers
- Local glyph set previously contained 768 files across these stacks.
- A Dart HTTP request to OpenFreeMap Noto Sans Regular glyph endpoint
  returned HTTP 200 and 76580 bytes.
- This does not prove MapLibre Native successfully loads those glyphs.
- Tests with local/online glyphs, vectors and sprites did not resolve
  the missing labels.
- Removing fontNames from the test annotation caused MapLibre to
  request Open Sans Regular,Arial Unicode MS Regular. This was the
  annotation's default stack, not the Liberty style's configured fonts.
- Updating maplibre_gl to 0.28.0 was proposed but NOT yet performed.

## Important diagnostics
- Do not use map.takeSnapshot() to inspect dynamically added layers.
  Android MapSnapshotter reloads the style separately.
- Use adb exec-out screencap -p for the actual live screen.
- getLayerProperties/getSourceProperties read serialized style JSON;
  dynamically added objects may return null.
- addGeoJsonSource can catch native exceptions while the method channel
  still completes successfully. An "ADDED" log does not prove rendering.

## Next steps
1. Restore the disposable probe from the previous conversation.
2. Recover or regenerate its required data/assets.
3. Recreate the Android emulator.
4. Establish a reproducible baseline.
5. Test maplibre_gl 0.28.0 separately from the 0.27.1 baseline.
6. Test online glyph loading and inspect native MapLibre glyph errors.
7. Only after the cause is established consider production changes.

## Rules
- Do not modify production geology-map unless explicitly requested.
- Keep probe changes isolated.
- Preserve data provenance, licenses and checksums.
- Do not reset or discard existing data repository changes.
- Do not commit or push without user approval.
