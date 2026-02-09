#!/bin/bash
set -e

# mi6 code agent entrypoint
# Expected files in /code:
#   - prompt.json: {"task": "..."}
#   - spec.txt or docs/specification.md: specification document
#   - files.json: list of RTL file paths (order matters!)
#   - sim.sh: simulation script (will be created if not present)

echo "=== mi6 code agent starting ==="
echo "Base URL: $MI6_BASE_URL"
echo "Model: $MI6_MODEL"
echo "Work dir: /code"

# Read task from prompt.json
if [ ! -f /code/prompt.json ]; then
  echo "ERROR: /code/prompt.json not found"
  exit 1
fi

TASK=$(jq -r '.task // .prompt // empty' /code/prompt.json)
if [ -z "$TASK" ]; then
  echo "ERROR: No task found in prompt.json"
  exit 1
fi

# Find spec document path
DOC_PATH=""
if [ -f /code/spec.txt ]; then
  DOC_PATH="/code/spec.txt"
elif [ -f /code/docs/specification.md ]; then
  DOC_PATH="/code/docs/specification.md"
elif [ -d /code/docs ] && [ "$(ls -A /code/docs 2>/dev/null)" ]; then
  # Concatenate all doc files into spec.txt
  cat /code/docs/* >/code/spec.txt 2>/dev/null || true
  DOC_PATH="/code/spec.txt"
else
  # Create spec.txt from task if no docs available
  echo "$TASK" >/code/spec.txt
  DOC_PATH="/code/spec.txt"
fi
echo "Using spec document: $DOC_PATH"

# Ensure files.json exists
FILES_JSON="/code/files.json"
if [ ! -f "$FILES_JSON" ]; then
  echo "Creating files.json from RTL and verif directories..."
  # Collect RTL files first, then verification files (order matters for simulation)
  {
    find /code/rtl -name "*.sv" -o -name "*.v" 2>/dev/null
    find /code/verif -name "*.sv" -o -name "*.v" 2>/dev/null
  } | jq -R -s 'split("\n") | map(select(length > 0))' >"$FILES_JSON"
fi
echo "Files list: $(cat $FILES_JSON)"

# Create simulation script if not present
SIM_SCRIPT="/code/sim.sh"
if [ ! -f "$SIM_SCRIPT" ]; then
  echo "Creating simulation script..."
  cat >"$SIM_SCRIPT" <<'SIMEOF'
#!/bin/bash
set -e
cd /code

# Read files from files.json (order matters!)
if [ ! -f files.json ]; then
    echo "ERROR: files.json not found"
    exit 1
fi

# Extract file list from JSON array
FILES=$(jq -r '.[]' files.json 2>/dev/null | tr '\n' ' ')
if [ -z "$FILES" ]; then
    echo "ERROR: No files found in files.json"
    exit 1
fi

echo "Simulation files (in order): $FILES"

# Detect available simulator and run
if command -v xrun &> /dev/null; then
    echo "Using Xcelium (xrun)..."
    xrun -64bit -sv -access +rwc $FILES 2>&1
elif command -v vcs &> /dev/null; then
    echo "Using VCS..."
    vcs -sverilog -full64 $FILES -o simv 2>&1 && ./simv 2>&1
elif command -v iverilog &> /dev/null; then
    echo "Using iverilog..."
    iverilog -g2012 -o sim.vvp $FILES 2>&1 && vvp sim.vvp 2>&1
elif command -v verilator &> /dev/null; then
    echo "Using Verilator..."
    verilator --binary -j 0 $FILES 2>&1
else
    echo "ERROR: No supported simulator found (xrun, vcs, iverilog, verilator)"
    exit 1
fi
SIMEOF
  chmod +x "$SIM_SCRIPT"
fi

# Ensure output directory exists
mkdir -p /code/src

# Run mi6 code agent
export PYDANTIC_DISABLE_PLUGINS=1

echo ""
echo "=== Running mi6 code agent ==="
echo "Task: ${TASK:0:200}..."
echo "Doc: $DOC_PATH"
echo "Files: $FILES_JSON"
echo "Sim: $SIM_SCRIPT"
echo ""

PYDANTIC_DISABLE_PLUGINS=1 /opt/mi6/bin/mi6 test_code_agent \
  --base-url "$MI6_BASE_URL" \
  --model "$MI6_MODEL" \
  --api-key "$MI6_API_KEY" \
  --doc "$DOC_PATH" \
  --files "$FILES_JSON" \
  --sim "$SIM_SCRIPT" \
  --task "$TASK" \
  --work-dir /code

echo ""
echo "=== mi6 code agent completed ==="

# List generated files
echo "Files in /code after agent run:"
find /code -name "*.sv" -o -name "*.v" 2>/dev/null | head -20
