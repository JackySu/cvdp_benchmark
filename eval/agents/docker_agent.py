"""Docker-based agent adapter for CVDP benchmark.

Runs an agent inside a Docker container with workspace directories mounted.
Compatible with existing Docker agents (mi6, custom agents).
"""

import os
import subprocess
import time

import yaml

from eval.agents.base import AgentAdapter, AgentResult, WorkspaceInfo
from eval.dataset import Datapoint
from eval.workspace import collect_changes, snapshot_workspace

from src.config_manager import config
from src.repository import DOCKER_TIMEOUT_AGENT


class DockerAgent(AgentAdapter):
    """Adapter for Docker-based agents."""

    def __init__(self, image: str, timeout: int = None, env: dict = None,
                 network_name: str = None):
        self.image = image
        self.timeout = timeout or DOCKER_TIMEOUT_AGENT or 600
        self.env = env or {}
        self.network_name = network_name

    def execute(self, workspace: WorkspaceInfo, dp: Datapoint) -> AgentResult:
        before = snapshot_workspace(workspace.issue_path)

        # Generate docker-compose-agent.yml
        compose_path = os.path.join(workspace.issue_path, "docker-compose-agent.yml")
        self._write_compose(compose_path, workspace, dp)

        # Generate run script
        script_path = os.path.join(workspace.issue_path, "run_docker_agent.sh")
        project_name = self._project_name(workspace)
        self._write_run_script(script_path, compose_path, project_name)

        log_file = os.path.join(workspace.report_path, f"{workspace.issue_id}_agent.txt")

        print(f"Running Docker agent: {self.image} in {workspace.issue_path}")

        try:
            with open(log_file, "w") as log:
                p = subprocess.Popen(
                    script_path, shell=True, stdout=log, stderr=subprocess.STDOUT
                )
                try:
                    p.communicate(timeout=self.timeout)
                    returncode = p.returncode
                except subprocess.TimeoutExpired:
                    print(f"Docker agent timed out after {self.timeout}s for {dp.id}")
                    p.kill()
                    # Try to stop compose
                    subprocess.run(
                        f"docker compose -f {compose_path} -p {project_name} kill agent",
                        shell=True, capture_output=True,
                    )
                    returncode = 1
        except Exception as e:
            return AgentResult(success=False, error=str(e), log_file=log_file)

        changes = collect_changes(workspace.issue_path, before)

        return AgentResult(
            success=(returncode == 0),
            modified_files=changes,
            log_file=log_file,
            error=f"Exit code {returncode}" if returncode != 0 else None,
        )

    def _project_name(self, workspace: WorkspaceInfo) -> str:
        safe = "".join(
            c.lower() if c.isalnum() or c in "-_" else "_"
            for c in workspace.datapoint_id
        )
        if not safe[0].isalnum():
            safe = "a" + safe
        return f"agent_{safe}_{int(time.time())}"

    def _write_compose(self, path: str, workspace: WorkspaceInfo, dp: Datapoint):
        compose = {
            "services": {
                "agent": {
                    "image": self.image,
                    "volumes": [
                        "./docs:/code/docs",
                        "./rtl:/code/rtl",
                        "./verif:/code/verif",
                        "./rundir:/code/rundir",
                        "./prompt.json:/code/prompt.json",
                    ],
                    "working_dir": "/code",
                    "environment": {},
                }
            }
        }

        # Pass API keys
        env = compose["services"]["agent"]["environment"]
        for key in ["OPENAI_USER_KEY", "ANTHROPIC_API_KEY", "DEEPSEEK_API_KEY"]:
            val = config.get(key, "")
            if val:
                env[key] = val
        env.update(self.env)

        # Network config
        if self.network_name:
            compose["networks"] = {"default": {"name": self.network_name, "external": True}}
            compose["services"]["agent"]["networks"] = ["default"]

        with open(path, "w") as f:
            yaml.dump(compose, f, default_flow_style=False)

    def _write_run_script(self, path: str, compose_path: str, project_name: str):
        script = f"""#!/bin/bash
set -e
cd "$(dirname "$0")"

cleanup() {{
    docker compose -f "{os.path.basename(compose_path)}" -p "{project_name}" down --remove-orphans 2>/dev/null || true
}}
trap cleanup EXIT

USER_ID=$(id -u)
GROUP_ID=$(id -g)

docker compose -f "{os.path.basename(compose_path)}" -p "{project_name}" run --rm --user "$USER_ID:$GROUP_ID" agent
EXIT_CODE=$?
exit $EXIT_CODE
"""
        with open(path, "w") as f:
            f.write(script)
        os.chmod(path, 0o755)
