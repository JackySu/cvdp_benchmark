#!/bin/bash
set -e

# Read prompt from prompt.json
if [ ! -f /code/prompt.json ]; then
  echo "ERROR: /code/prompt.json not found"
  exit 1
fi

PROMPT=$(jq -r '.prompt' /code/prompt.json)
if [ -z "$PROMPT" ] || [ "$PROMPT" = "null" ]; then
  echo "ERROR: No prompt found in prompt.json"
  exit 1
fi

# Ensure output directory exists
mkdir -p /code/src

# Run mi6 code agent
export PYDANTIC_DISABLE_PLUGINS=1

echo "Running mi6 code agent..."
echo "Base URL: $MI6_BASE_URL"
echo "Model: $MI6_MODEL"

/opt/mi6/bin/mi6 test_code_agent \
  --base-url "$MI6_BASE_URL" \
  --model "$MI6_MODEL" \
  --api-key "$MI6_API_KEY" \
  --task "$PROMPT" \
  --work-dir /code

# recursively list all files in /code
ls -laR /code

# Check if output was generated
if [ -f /code/out.sv ]; then
  echo "SUCCESS: Generated /code/out.sv"
  echo "--- Generated code preview (first 50 lines) ---"
  head -50 /code/out.sv
else
  echo "ERROR: mi6 did not generate /code/out.sv"
  exit 1
fi
