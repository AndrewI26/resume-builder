#!/usr/bin/env bash
#
# Builds the TeX distribution the desktop app ships with.
#
#   apps/desktop/scripts/bundle-texlive.sh [destination]
#
# The app cannot assume pdfTeX is installed — most people have never had a
# reason to install LaTeX — and the whole point of the desktop build is that it
# works with nothing else set up. So it carries its own.
#
# This is the recipe from apps/api/Dockerfile, which is the one already proven
# to typeset these resumes: TinyTeX plus exactly the packages the preamble
# loads. A full TeX Live is several gigabytes; a Debian texlive-full pulls in
# gigabytes of fonts for the sake of two symbols. This is a few hundred
# megabytes, and every package in it is one the template names.
#
# The engine has to be pdfTeX. The template calls \pdfgentounicode, which is a
# pdfTeX primitive, and it is what makes the PDF readable by applicant tracking
# systems — for a resume, close to the whole point. XeTeX-based engines such as
# Tectonic reject it.

set -euo pipefail

DESTINATION="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/resources/texlive}"

# Exactly the list apps/api/Dockerfile installs. Keep the two in step: they
# typeset the same document with the same preamble.
PACKAGES=(
  tools
  preprint
  titlesec
  marvosym
  enumitem
  fancyhdr
  babel-english
  fontawesome5
  xcolor
)

if [ -n "$(find "$DESTINATION/bin" -name pdflatex 2>/dev/null | head -1)" ]; then
  echo "TeX already bundled at $DESTINATION"
  exit 0
fi

WORKSPACE="$(mktemp -d)"
trap 'rm -rf "$WORKSPACE"' EXIT

echo "Installing TinyTeX into a scratch directory..."
# TINYTEX_DIR rather than redirecting HOME: the installer picks
# ~/Library/TinyTeX on macOS and ~/.TinyTeX elsewhere, and a build that leaves
# a TeX distribution in somebody's home directory is a surprising build.
INSTALLED="$WORKSPACE/TinyTeX"
export TINYTEX_DIR="$WORKSPACE"
curl -fsSL https://yihui.org/tinytex/install-bin-unix.sh | sh

if [ ! -d "$INSTALLED" ]; then
  echo "TinyTeX did not install where expected ($INSTALLED)" >&2
  exit 1
fi

# The binaries sit under a platform-named directory — universal-darwin,
# x86_64-linux, and so on.
#
# That directory is left exactly where it is. TeX finds its own files by
# walking up from the binary that is running: the format file pdfTeX needs is
# resolved relative to $SELFAUTOPARENT, two levels above bin/<platform>/.
# Flattening this to a plain bin/ was tried, so that the app would have one
# fixed path to point at, and it moves every one of those lookups a directory
# too high — pdfTeX then cannot find its own pdflatex.fmt and tries to rebuild
# it at compile time. The shell finds the platform directory instead.
BIN_DIR="$(find "$INSTALLED/bin" -maxdepth 1 -mindepth 1 -type d | head -1)"
export PATH="$BIN_DIR:$PATH"

echo "Installing the packages the template needs..."
tlmgr install "${PACKAGES[@]}"

# None of this is read by pdfTeX, and it is most of the size.
rm -rf \
  "$INSTALLED/texmf-dist/doc" \
  "$INSTALLED/texmf-dist/source" \
  "$INSTALLED/tlpkg/tlpobj"

mkdir -p "$(dirname "$DESTINATION")"
rm -rf "$DESTINATION"
mv "$INSTALLED" "$DESTINATION"

BUNDLED_PDFLATEX="$(find "$DESTINATION/bin" -name pdflatex | head -1)"
echo "Bundled TeX at $DESTINATION ($(du -sh "$DESTINATION" | cut -f1))"
"$BUNDLED_PDFLATEX" --version | head -1
