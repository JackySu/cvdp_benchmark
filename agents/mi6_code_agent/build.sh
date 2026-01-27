#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

IMAGE_NAME="${1:-mi6_code_agent}"
IMAGE_TAG="${2:-latest}"

echo "Building mi6_code_agent Docker image..."
echo "Project root: $PROJECT_ROOT"
echo "Image: $IMAGE_NAME:$IMAGE_TAG"

# Check if mi6 binary exists
MI6_BIN="$PROJECT_ROOT/bin/mi6"
if [ ! -f "$MI6_BIN" ]; then
    echo "ERROR: mi6 binary not found at $MI6_BIN"
    exit 1
fi

# Create temporary build context
BUILD_DIR=$(mktemp -d)
trap "rm -rf $BUILD_DIR" EXIT

# Copy files to build context
cp "$SCRIPT_DIR/Dockerfile" "$BUILD_DIR/"
cp "$SCRIPT_DIR/entrypoint.sh" "$BUILD_DIR/"
mkdir -p "$BUILD_DIR/bin"
cp "$MI6_BIN" "$BUILD_DIR/bin/mi6"

# Build the image
docker build -t "$IMAGE_NAME:$IMAGE_TAG" "$BUILD_DIR"

echo ""
echo "Build complete: $IMAGE_NAME:$IMAGE_TAG"
echo ""
echo "Usage with CVDP benchmark:"
echo "  python run_benchmark.py --llm --agent $IMAGE_NAME:$IMAGE_TAG --filename <dataset.jsonl>"
echo ""
echo "Environment variables (set via docker-compose or -e flag):"
echo "  MI6_BASE_URL  - API base URL (default: https://api.deepseek.com/)"
echo "  MI6_MODEL     - Model name (default: deepseek:deepseek-reasoner)"
echo "  MI6_API_KEY   - API key (required)"
echo "  MI6_TIMEOUT   - Timeout in seconds (default: 300)"
