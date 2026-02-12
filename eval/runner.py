"""Benchmark orchestrator for CVDP evaluation.

Coordinates the full pipeline: load dataset → prepare workspace →
run agent/LLM → execute test harness → collect results → report.
"""

import json
import os
import queue
import sys

from eval.agents.base import AgentAdapter, AgentResult, WorkspaceInfo
from eval.dataset import Datapoint, load_dataset
from eval.harness import TestResult, run_tests
from eval.workspace import apply_golden_patches, setup_workspace

from src.config_manager import config
from src.parallel_executor import ParallelExecutor


class GoldenAgent(AgentAdapter):
    """Pseudo-agent that applies golden reference patches (for validation)."""

    def execute(self, workspace: WorkspaceInfo, dp: Datapoint) -> AgentResult:
        return AgentResult(success=True, modified_files=dp.expected_patches)


class BenchmarkRunner:
    """Orchestrates benchmark execution across datapoints."""

    def __init__(
        self,
        dataset_path: str,
        agent: AgentAdapter,
        prefix: str = "work",
        threads: int = 1,
        network_name: str = None,
        sbj_llm_model=None,
    ):
        self.dataset_path = dataset_path
        self.datapoints = load_dataset(dataset_path)
        self.agent = agent
        self.prefix = prefix
        self.threads = threads
        self.network_name = network_name
        self.sbj_llm_model = sbj_llm_model

    def run_single(self, datapoint_id: str) -> dict:
        """Run benchmark for a single datapoint. Returns result dict."""
        dp = self.datapoints[datapoint_id]
        workspace = setup_workspace(dp, self.prefix)

        print(f"Processing {dp.id} (cat={dp.categories[0]}, diff={dp.difficulty})")
        agent_result = self.agent.execute(workspace, dp)

        if not agent_result.success:
            print(f"Agent failed for {dp.id}: {agent_result.error}")

        test_result = run_tests(
            workspace, dp, agent_result,
            sbj_llm_model=self.sbj_llm_model,
            network_name=self.network_name,
        )

        result = test_result.to_dict()
        if agent_result.log_file:
            result["agent_logfile"] = agent_result.log_file
        if agent_result.error:
            result["agent_error"] = agent_result.error

        return result

    def _th_run_single(self, dp_id: str, result_queue: queue.Queue = None):
        """Thread worker for parallel execution."""
        try:
            result = self.run_single(dp_id)
            if result_queue:
                result_queue.put({dp_id: result})
        except Exception as e:
            error_result = {
                "category": self.datapoints[dp_id].categories[0] if dp_id in self.datapoints else "unknown",
                "difficulty": self.datapoints[dp_id].difficulty if dp_id in self.datapoints else "unknown",
                "tests": [{"result": 1, "log": None, "error_msg": str(e), "execution": 0.0}],
                "errors": 1,
            }
            if result_queue:
                result_queue.put({dp_id: error_result})

    def run_all(self) -> dict:
        """Run benchmark for all datapoints. Returns {id: result} dict."""
        ids = list(self.datapoints.keys())
        print(f"Running benchmark on {len(ids)} datapoints with {self.threads} threads")

        if self.threads <= 1:
            results = {}
            for dp_id in ids:
                results[dp_id] = self.run_single(dp_id)
            return results

        executor = ParallelExecutor(num_workers=self.threads, phase_name="Benchmark")
        results = executor.execute_parallel_with_results(
            task_func=self._th_run_single,
            items=ids,
        )
        return results

    def save_results(self, results: dict, path: str = None):
        """Save raw results to JSON file."""
        if path is None:
            path = os.path.join(self.prefix, "raw_result.json")
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as f:
            json.dump(results, f, indent=2)
        print(f"Results saved to {path}")
