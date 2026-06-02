#!/usr/bin/env bash
# Build a self-contained LIF Studio .deb (Debian/Ubuntu) using PyInstaller.
#
#   bash packaging/build_deb.sh
#
# Output: dist/lif-studio_<version>_amd64.deb
# Requires: pyinstaller (pip install pyinstaller), dpkg-deb.
set -euo pipefail

VERSION="2.0.0"
PKG="lif-studio"
ARCH="$(dpkg --print-architecture 2>/dev/null || echo amd64)"

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> Building frozen bundle with PyInstaller"
# Use the active interpreter's PyInstaller (the `pyinstaller` launcher may point
# at a different Python that doesn't have it installed).
PY="${PYTHON:-python3}"
"$PY" -m PyInstaller --noconfirm --clean packaging/lif_studio.spec

BUNDLE="dist/lif-studio"
[ -d "$BUNDLE" ] || { echo "ERROR: $BUNDLE not produced"; exit 1; }

echo "==> Staging .deb tree"
STAGE="build/deb/${PKG}_${VERSION}_${ARCH}"
rm -rf "$STAGE"
mkdir -p "$STAGE/DEBIAN" \
         "$STAGE/opt/lif-studio" \
         "$STAGE/usr/bin" \
         "$STAGE/usr/share/applications" \
         "$STAGE/usr/share/icons/hicolor/256x256/apps"

cp -r "$BUNDLE/." "$STAGE/opt/lif-studio/"
ln -sf /opt/lif-studio/lif-studio "$STAGE/usr/bin/lif-studio"
cp packaging/lif-studio.desktop "$STAGE/usr/share/applications/"
cp packaging/icon.png "$STAGE/usr/share/icons/hicolor/256x256/apps/lif-studio.png"

INSTALLED_KB="$(du -sk "$STAGE/opt" | cut -f1)"
cat > "$STAGE/DEBIAN/control" <<EOF
Package: ${PKG}
Version: ${VERSION}
Section: science
Priority: optional
Architecture: ${ARCH}
Maintainer: LIF Studio <noreply@example.com>
Installed-Size: ${INSTALLED_KB}
Depends: libc6, libglib2.0-0, libgl1
Description: LIF Studio — Leica LIF to colored TIFF converter and analyzer
 Convert Leica .lif microscopy files into colored TIFF overlays with
 configurable per-type channel colors, and run quantitative analysis
 (intensity, % area, object counts, colocalization) on the raw channels.
EOF

echo "==> Building package"
mkdir -p dist
DEB="dist/${PKG}_${VERSION}_${ARCH}.deb"
dpkg-deb --build --root-owner-group "$STAGE" "$DEB"

echo "==> Done: $DEB"
dpkg-deb --info "$DEB" | sed 's/^/    /'
echo
echo "Install with:  sudo apt install ./$DEB     (or: sudo dpkg -i $DEB)"
