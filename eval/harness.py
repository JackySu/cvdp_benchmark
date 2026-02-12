"""Test harness execution for CVDP benchmark.

Wraps src/repository.py to run objective (Docker-based) and subjective
(ROUGE/BLEU/LLM) tests against agent-modified workspaces.
"""

import json
import os
from dataclasses import dataclass, field

from eval.agents.base import AgentResult, WorkspaceInfo
from eval.dataset import Datapoint
from eval.workspace import _restore_files

from src.constants import CODE_COMPREHENSION_CATEGORIES
from src.repository import Repository


@dataclass
class TestResult:
    category: str
    difficulty: str
    tests: list = field(default_factory=list)
    errors: int = 0

    @property
    def passed(self) -> bool:
        return self.errors == 0 and all(t.get("result", 1) == 0 for t in self.tests)

    def to_dict(self) -> dict:
        return {
            "category": self.category,
            "difficulty": self.difficulty,
            "tests": self.tests,
            "errors": self.errors,
        }


def _build_harness_files(dp: Datapoint) -> dict:
    """Extract harness files dict from datapoint, handling format differences."""
    h = dp.harness
    if not h:
        return {}
    # Copilot format nests under "files"
    if "files" in h and isinstance(h["files"], dict):
        return h["files"]
    # Agentic format: harness is already {filename: content}
    # but may contain non-file keys like "docker-compose.yml"
    return {k: v for k, v in h.items() if isinstance(v, str)}


def run_tests(
    workspace: WorkspaceInfo,
    dp: Datapoint,
    agent_result: AgentResult,
    sbj_llm_model=None,
    network_name: str = None,
) -> TestResult:
    """Run the test harness for a datapoint after agent execution.

    1. Applies agent's modified files to the workspace
    2. Creates a Repository instance
    3. Runs objective or subjective tests
    4. Returns TestResult
    """
    # Apply agent modifications to workspace
    if agent_result.modified_files:
        _restore_files(workspace.issue_path, agent_result.modified_files)

    # Build the context dict (what's currently on disk in the workspace)
    context_files = _read_workspace_files(workspace.issue_path)
    harness_files = _build_harness_files(dp)
    patches = list(dp.expected_patches.keys())

    # Parse repo name from workspace path
    repo_name = os.path.dirname(os.path.dirname(workspace.issue_path))  # up from harness/{id}

    # Create Repository — it calls prepare() internally which restores files
    # We already have files on disk, so pass them as context
    repo = Repository(
        repo=repo_name,
        id=workspace.issue_id,
        context=context_files,
        harness=harness_files,
        patches=patches,
        sbj_llm_model=sbj_llm_model,
        network_name=network_name,
    )

    cat_id = dp.category_id

    if dp.is_comprehension:
        tests, errors = _run_subjective(repo, dp, context_files, sbj_llm_model)
    else:
        repo.debug = False
        tests, errors = repo.obj()

    return TestResult(
        category=dp.categories[0] if dp.categories else f"cid{cat_id:03d}",
        difficulty=dp.difficulty,
        tests=tests,
        errors=errors,
    )


def _run_subjective(repo, dp: Datapoint, context_files: dict, sbj_llm_model) -> tuple:
    """Run subjective scoring for comprehension tasks."""
    # Find the response content
    response = None
    for key in ["subjective.txt", "docs/subjective.txt"]:
        if key in context_files:
            response = context_files[key]
            break

    if not response:
        return [{"result": 1, "log": None, "error_msg": "No content for subjective scoring", "execution": 0.0}], 1

    reference = dp.subjective_reference or ""
    cat_id = dp.category_id

    # Extract problem prompt for LLM scoring context
    problem_prompt = dp.prompt

    return repo.sbj(response, reference, cat_id, problem_prompt)


def _read_workspace_files(issue_path: str) -> dict[str, str]:
    """Read all files from workspace into a dict."""
    files = {}
    for subdir in ["rtl", "verif", "docs", "src", "rundir"]:
        dir_path = os.path.join(issue_path, subdir)
        if not os.path.isdir(dir_path):
            continue
        for root, _, filenames in os.walk(dir_path):
            for fname in filenames:
                full = os.path.join(root, fname)
                rel = os.path.relpath(full, issue_path)
                try:
                    with open(full, "r", encoding="utf-8", errors="replace") as f:
                        files[rel] = f.read()
                except Exception:
                    pass
    return files
