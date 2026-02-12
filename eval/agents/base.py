"""Agent adapter interface for CVDP benchmark.

All agent types (host CLI, Docker, LLM API) implement this interface
so the benchmark runner can treat them uniformly.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from eval.dataset import Datapoint


@dataclass
class WorkspaceInfo:
    """Information about a prepared workspace for a datapoint."""
    issue_path: str       # e.g. work/cvdp_64b66b_codec/harness/1/
    repo_path: str        # e.g. work/cvdp_64b66b_codec/
    report_path: str      # e.g. work/cvdp_64b66b_codec/reports/
    prompt_path: str      # e.g. work/cvdp_64b66b_codec/harness/1/prompt.json
    issue_id: int         # numeric issue id
    datapoint_id: str     # full datapoint id string


@dataclass
class AgentResult:
    """Result from an agent execution."""
    success: bool
    modified_files: dict = field(default_factory=dict)  # {filepath: new_content}
    log_file: str | None = None
    patch_file: str | None = None
    error: str | None = None


class AgentAdapter(ABC):
    """Base class for all agent adapters."""

    @abstractmethod
    def execute(self, workspace: WorkspaceInfo, datapoint: Datapoint) -> AgentResult:
        """Run the agent on the prepared workspace."""
        ...
