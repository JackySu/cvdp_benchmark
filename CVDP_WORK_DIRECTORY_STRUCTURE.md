# CVDP Benchmark Work Directory Structure

This document explains the directory structure of CVDP benchmark work directories (e.g., `work_1.0.2_agentic_code_generation_commercial`).

## Overview

When running the CVDP benchmark with an agent, the framework creates a work directory with the following structure:

```
work_<version>_<benchmark_type>/
├── cvdp_agentic_<design_name>/           # One directory per design
│   ├── harness/
│   │   └── <issue_id>/                   # One directory per test case
│   │       ├── docs/                     # Design specifications
│   │       ├── rtl/                      # RTL files (agent-generated go here)
│   │       ├── verif/                    # Testbench files
│   │       ├── src/                      # Reference RTL and test harness
│   │       ├── rundir/                   # Simulation output
│   │       ├── before/                   # Snapshot before agent runs (if agent used)
│   │       ├── prompt.json               # Task prompt for the agent
│   │       ├── agent_changes.patch       # Diff of agent changes (if agent used)
│   │       ├── docker-compose.yml        # Harness docker config
│   │       └── docker-compose-agent.yml  # Agent docker config (if agent used)
│   └── reports/
│       ├── <issue_id>.txt                # Harness test output
│       └── <issue_id>_agent.txt          # Agent execution log (if agent used)
```

## Key Locations

### 1. Agent-Generated RTL Files

**Location:** `<work_dir>/cvdp_agentic_<design>/harness/<issue_id>/rtl/`

After the agent runs, generated RTL files are placed in the `rtl/` directory. For example:
```
work_1.0.2_agentic_code_generation_no_commercial/
└── cvdp_agentic_fixed_arbiter/
    └── harness/10/
        └── rtl/
            └── fixed_priority_arbiter.sv   # Agent-generated RTL
```

### 2. Original RTL (Before Agent Modification)

**Location:** `<work_dir>/cvdp_agentic_<design>/harness/<issue_id>/before/rtl/`

The `before/` directory contains a snapshot of all files before the agent runs. This allows comparison of original vs. modified files.

### 3. Design Specifications

**Location:** `<work_dir>/cvdp_agentic_<design>/harness/<issue_id>/docs/specification.md`

Contains the detailed design specification that describes:
- Module functionality
- Interface signals
- Timing requirements
- Expected behavior

### 4. Task Prompt (Original Task Specification)

**Location:** `<work_dir>/cvdp_agentic_<design>/harness/<issue_id>/prompt.json`

Contains the task prompt given to the agent. Format:
```json
{
  "prompt": "I need to implement a **fixed priority arbiter** module..."
}
```

**To extract the task prompt:**
```bash
# Using jq
jq -r '.prompt' <work_dir>/cvdp_agentic_<design>/harness/<issue_id>/prompt.json

# Using Python
python3 -c "import json; print(json.load(open('prompt.json'))['prompt'])"
```

### 5. Agent Changes (Diff/Patch)

**Location:** `<work_dir>/cvdp_agentic_<design>/harness/<issue_id>/agent_changes.patch`

Contains a unified diff showing what the agent changed. Format:
```diff
--- a/rtl/module_name.sv
+++ b/rtl/module_name.sv
@@ -1,10 +1,15 @@
-original code
+modified code
```

### 6. Testbench Files

**Location:** `<work_dir>/cvdp_agentic_<design>/harness/<issue_id>/verif/`

Contains SystemVerilog testbenches that verify the RTL:
- `*_tb.sv` - SystemVerilog testbench
- Used by cocotb or direct simulation

### 7. Reference RTL and Test Harness

**Location:** `<work_dir>/cvdp_agentic_<design>/harness/<issue_id>/src/`

Contains:
- Reference RTL modules (provided as context)
- Python test harness files (`process.py`, `test_*.py`)
- Environment configuration (`.env`)

### 8. Test Reports

**Location:** `<work_dir>/cvdp_agentic_<design>/reports/`

- `<issue_id>.txt` - Harness test output (simulation results)
- `<issue_id>_agent.txt` - Agent execution log (what the agent did)

## Example: Extracting Information

### Extract all task prompts from a work directory:
```bash
for f in work_*/cvdp_*/harness/*/prompt.json; do
  echo "=== $f ==="
  jq -r '.prompt' "$f" | head -20
  echo ""
done
```

### Find all agent-generated RTL files:
```bash
find work_*/ -path "*/harness/*/rtl/*.sv" -type f
```

### View agent changes for a specific test:
```bash
cat work_*/cvdp_agentic_<design>/harness/<issue_id>/agent_changes.patch
```

### Compare original vs. modified RTL:
```bash
diff -u work_*/cvdp_*/harness/<id>/before/rtl/*.sv \
        work_*/cvdp_*/harness/<id>/rtl/*.sv
```

## Directory Presence by Run Type

| Directory/File | Golden Run | Agent Run |
|----------------|------------|-----------|
| `docs/` | ✓ | ✓ |
| `rtl/` | ✓ (may be empty) | ✓ (agent output) |
| `verif/` | ✓ | ✓ |
| `src/` | ✓ | ✓ |
| `before/` | ✗ | ✓ |
| `prompt.json` | ✓ | ✓ |
| `agent_changes.patch` | ✗ | ✓ |
| `docker-compose-agent.yml` | ✗ | ✓ |
| `reports/<id>_agent.txt` | ✗ | ✓ |

## Notes

1. **Commercial vs Non-Commercial**: Commercial benchmarks may use Cadence xrun simulator in addition to iverilog
2. **Issue IDs**: Each design can have multiple test cases (issues), numbered sequentially
3. **Empty RTL directory**: If the agent failed to generate RTL, the `rtl/` directory may be empty
4. **Patch format**: The `agent_changes.patch` uses unified diff format compatible with `patch -p1`
