"""Host CLI agent adapter for CVDP benchmark.

Runs a CLI command (e.g. cline, opencode) on the host machine with the
workspace directory as the working directory. The agent reads prompt.json,
modifies files in place, and exits. The benchmark diffs before/after.
"""

import os
import subprocess

from eval.agents.base import AgentAdapter, AgentResult, WorkspaceInfo
from eval.dataset import Datapoint
from eval.workspace import collect_changes, snapshot_workspace

from src.config_manager import config


class HostCLIAgent(AgentAdapter):
    """Adapter for CLI-based agents running on the host (Cline, OpenCode, etc.)."""

    def __init__(self, command: str, timeout: int = 600, env: dict = None):
        self.command = command
        self.timeout = timeout
        self.env = env or {}

    def execute(self, workspace: WorkspaceInfo, dp: Datapoint) -> AgentResult:
        # Snapshot before state
        before = snapshot_workspace(workspace.issue_path)

        # Build environment
        env = os.environ.copy()
        env.update({
            "CVDP_PROMPT_FILE": workspace.prompt_path,
            "CVDP_WORK_DIR": workspace.issue_path,
            "CVDP_DATAPOINT_ID": dp.id,
        })
        # Pass through API keys
        for key in ["OPENAI_USER_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY"]:
            val = config.get(key, "")
            if val:
                env[key] = val
        env.update(self.env)

        # Log file
        log_file = os.path.join(workspace.report_path, f"{workspace.issue_id}_agent.txt")

        print(f"Running host CLI agent: {self.command} (cwd={workspace.issue_path})")

        try:
            with open(log_file, "w") as log:
                result = subprocess.run(
                    self.command,
                    shell=True,
                    cwd=workspace.issue_path,
                    env=env,
                    stdout=log,
                    stderr=subprocess.STDOUT,
                    timeout=self.timeout,
                )
            returncode = result.returncode
        except subprocess.TimeoutExpired:
            print(f"Agent timed out after {self.timeout}s for {dp.id}")
            return AgentResult(
                success=False,
                error=f"Agent timed out after {self.timeout}s",
                log_file=log_file,
            )
        except Exception as e:
            return AgentResult(success=False, error=str(e), log_file=log_file)

        # Collect changes
        changes = collect_changes(workspace.issue_path, before)

        if returncode != 0:
            print(f"Agent exited with code {returncode} for {dp.id}")

        return AgentResult(
            success=(returncode == 0),
            modified_files=changes,
            log_file=log_file,
            error=f"Exit code {returncode}" if returncode != 0 else None,
        )
