#!/usr/bin/env bash
set -euo pipefail

MODEL_DIR="$(dirname "$0")/../models/sherpa"
mkdir -p "$MODEL_DIR"

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 <model-archive-url>"
  echo "Example: $0 https://example.com/sherpa-transducer-english.zip"
  exit 1
fi

URL="$1"
FNAME=$(basename "$URL")
TARGET="$MODEL_DIR/$FNAME"

echo "Downloading $URL to $TARGET"
curl -L -o "$TARGET" "$URL"

case "$TARGET" in
  *.zip)
    echo "Unzipping $TARGET into $MODEL_DIR"
    unzip -o "$TARGET" -d "$MODEL_DIR"
    rm -f "$TARGET"
    ;;
  *.tar.gz|*.tgz)
    echo "Extracting $TARGET into $MODEL_DIR"
    tar -xzf "$TARGET" -C "$MODEL_DIR"
    rm -f "$TARGET"
    ;;
  *)
    echo "Downloaded file saved to $TARGET. Please extract or move files into $MODEL_DIR as needed."
    ;;
esac

echo "Done. Models in $MODEL_DIR"
