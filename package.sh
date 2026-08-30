#!/bin/bash
# =============================================================================
# Skrypt pakujący wtyczkę MSA: ShadowCaster do pliku ZIP (zgodny z plugins.qgis.org)
# =============================================================================

set -e

PLUGIN_DIR="$(cd "$(dirname "$0")" && pwd)"
VERSION=$(grep "^version=" "$PLUGIN_DIR/metadata.txt" | cut -d= -f2 | tr -d ' \r\n')
ZIP_NAME="msa_shadowcaster.${VERSION}.zip"
OUT_DIR="$PLUGIN_DIR/dist"

echo "=== Pakowanie wtyczki MSA: ShadowCaster (wersja $VERSION) ==="

mkdir -p "$OUT_DIR"
rm -f "$OUT_DIR/$ZIP_NAME"

TMP_STAGE="$(mktemp -d)"
mkdir -p "$TMP_STAGE/msa_shadowcaster"

# Kopiowanie tylko niezbędnych plików produkcyjnych
cp "$PLUGIN_DIR/metadata.txt" "$TMP_STAGE/msa_shadowcaster/"
cp "$PLUGIN_DIR/__init__.py" "$TMP_STAGE/msa_shadowcaster/"
cp "$PLUGIN_DIR/plugin.py" "$TMP_STAGE/msa_shadowcaster/"
cp "$PLUGIN_DIR/shadow_provider.py" "$TMP_STAGE/msa_shadowcaster/"
cp "$PLUGIN_DIR/shadow_algorithm.py" "$TMP_STAGE/msa_shadowcaster/"
cp "$PLUGIN_DIR/icon.png" "$TMP_STAGE/msa_shadowcaster/"
cp "$PLUGIN_DIR/README.md" "$TMP_STAGE/msa_shadowcaster/"
cp "$PLUGIN_DIR/LICENSE" "$TMP_STAGE/msa_shadowcaster/"

# Usunięcie zbędnych plików systemowych
find "$TMP_STAGE" -name ".DS_Store" -delete 2>/dev/null || true
find "$TMP_STAGE" -name "._*" -delete 2>/dev/null || true
find "$TMP_STAGE" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# Budowa archiwum ZIP
(cd "$TMP_STAGE" && zip -r "$OUT_DIR/$ZIP_NAME" msa_shadowcaster -x "*.git*" "*__pycache__*" "*.DS_Store*")

rm -rf "$TMP_STAGE"

echo "✓ Wygenerowano paczkę produkcyjną:"
echo "  -> $OUT_DIR/$ZIP_NAME"
echo "Gotowa do wgrania na: https://plugins.qgis.org/plugins/add/"
