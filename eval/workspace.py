"""Workspace setup and file management for CVDP benchmark.

Handles creating the directory structure, restoring context files,
writing prompt.json, and diffing before/after agent execution.
"""

import json
import os
import shutil

from eval.agents.base import WorkspaceInfo
from eval.dataset import Datapoint


def _parse_name_and_issue(dp: Datapoint) -> tuple[str, int]:
    """Extract the repo name stem and numeric issue id from a datapoint id.

    Example: 'cvdp_agentic_64b66b_codec_0001' -> ('agentic_64b66b_codec', 1)
             'cvdp_copilot_16qam_mapper_0001' -> ('copilot_16qam_mapper', 1)
    """
    parts = dp.id.split("_")
    # parts[0] = 'cvdp', parts[1:-1] = name segments, parts[-1] = issue number
    name_stem = "_".join(parts[1:-1])
    issue_id = int(parts[-1])
    return name_stem, issue_id


def setup_workspace(dp: Datapoint, prefix: str) -> WorkspaceInfo:
    """Create the working directory for a datapoint and restore its files."""
    name_stem, issue_id = _parse_name_and_issue(dp)
    repo_path = os.path.join(prefix, f"cvdp_{name_stem}")
    issue_path = os.path.join(repo_path, "harness", str(issue_id))
    report_path = os.path.join(repo_path, "reports")
    prompt_path = os.path.join(issue_path, "prompt.json")

    # Create directory structure
    for d in [repo_path, os.path.join(repo_path, "harness"), report_path]:
        os.makedirs(d, exist_ok=True)
    for sub in ["rtl", "verif", "docs", "src", "rundir"]:
        os.makedirs(os.path.join(issue_path, sub), exist_ok=True)

    # Restore context files
    _restore_files(issue_path, dp.context_files)

    # Restore harness files
    harness_files = dp.harness
    if isinstance(harness_files, dict):
        # Copilot format has harness.files, agentic has harness directly
        if "files" in harness_files and isinstance(harness_files["files"], dict):
            harness_files = harness_files["files"]
        _restore_files(issue_path, harness_files)

    # Write prompt.json
    prompt_data = {"prompt": dp.prompt}
    if dp.system_message:
        prompt_data["system_message"] = dp.system_message
    with open(prompt_path, "w", encoding="utf-8") as f:
        json.dump(prompt_data, f, indent=2)

    return WorkspaceInfo(
        issue_path=os.path.abspath(issue_path),
        repo_path=os.path.abspath(repo_path),
        report_path=os.path.abspath(report_path),
        prompt_path=os.path.abspath(prompt_path),
        issue_id=issue_id,
        datapoint_id=dp.id,
    )


def _restore_files(base_path: str, files: dict):
    """Write files dict to disk under base_path."""
    for filepath, content in files.items():
        if not isinstance(content, str):
            continue
        full_path = os.path.join(base_path, filepath)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)


def snapshot_workspace(issue_path: str) -> dict[str, str]:
    """Capture current file contents under issue_path (excluding prompt.json).

    Returns {relative_path: content} for all files in rtl/, verif/, docs/.
    """
    snapshot = {}
    for subdir in ["rtl", "verif", "docs"]:
        dir_path = os.path.join(issue_path, subdir)
        if not os.path.isdir(dir_path):
            continue
        for root, _, filenames in os.walk(dir_path):
            for fname in filenames:
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, issue_path)
                try:
                    with open(full, "r", encoding="utf-8", errors="replace") as f:
                        snapshot[rel] = f.read()
                except Exception:
                    pass
    return snapshot


def collect_changes(issue_path: str, before: dict[str, str]) -> dict[str, str]:
    """Compare current workspace state against a before snapshot.

    Returns {relative_path: new_content} for all added or modified files.
    """
    after = snapshot_workspace(issue_path)
    changes = {}
    for path, content in after.items():
        if path not in before or before[path] != content:
            changes[path] = content
    return changes


def apply_golden_patches(workspace: WorkspaceInfo, dp: Datapoint):
    """Apply golden reference patches to the workspace (for golden mode)."""
    _restore_files(workspace.issue_path, dp.expected_patches)
