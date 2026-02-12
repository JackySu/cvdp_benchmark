#!/usr/bin/env python3
"""CVDP Benchmark evaluation entrypoint.

Usage examples:
  # Golden mode (validate test harness with reference solutions):
  python -m eval.main -f dataset.jsonl -p work_test

  # LLM non-agentic mode (direct API call, no agent):
  python -m eval.main -f dataset.jsonl --model gpt-4o -p work_llm

  # Agent on host (e.g. opencode, cline):
  python -m eval.main -f dataset.jsonl --agent opencode \
    --model deepseek-reasoner --api-key sk-xxx --base-url https://api.deepseek.com

  # Agent in Docker container:
  python -m eval.main -f dataset.jsonl --agent opencode \
    --docker-image mi6_code_agent:latest \
    --model deepseek-reasoner --api-key sk-xxx --base-url https://api.deepseek.com

  # Single datapoint:
  python -m eval.main -f dataset.jsonl --agent opencode --model deepseek-reasoner \
    --id cvdp_agentic_64b66b_codec_0001
"""

import argparse
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

from src.config_manager import config
from src import report


def parse_args():
    parser = argparse.ArgumentParser(
        description="CVDP Benchmark Evaluation",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )

    parser.add_argument("-f", "--filename", required=True, help="Dataset JSONL file path")
    parser.add_argument("-p", "--prefix", default=config.get("BENCHMARK_PREFIX"), help="Output directory prefix")
    parser.add_argument("--id", type=str, help="Run a single datapoint by ID")
    parser.add_argument("-t", "--threads", type=int, default=config.get("BENCHMARK_THREADS"), help="Parallel threads")

    # Agent config
    parser.add_argument("--agent", type=str, help="Agent command to run (e.g. 'opencode', 'cline', './my_agent.sh')")
    parser.add_argument("--docker-image", type=str, help="Run agent inside this Docker image instead of on host")

    # LLM / API config
    parser.add_argument("--model", type=str, help="LLM model name (e.g. 'gpt-4o', 'deepseek-reasoner')")
    parser.add_argument("--api-key", type=str, help="API key for the LLM provider")
    parser.add_argument("--base-url", type=str, help="Base URL for OpenAI-compatible API")
    parser.add_argument("--custom-factory", type=str, help="Path to custom model factory Python file")

    # General options
    parser.add_argument("--timeout", type=int, default=600, help="Agent timeout in seconds (default: 600)")
    parser.add_argument("--network-name", type=str, help="Docker network name for test harness")
    parser.add_argument("--regenerate-report", action="store_true", help="Regenerate report from existing raw_result.json")

    args = parser.parse_args()

    # Validation
    if args.docker_image and not args.agent:
        parser.error("--docker-image requires --agent")

    return args


def build_agent(args):
    """Build the appropriate agent adapter from CLI args.

    Logic:
      --agent + --docker-image  → DockerAgent (containerized)
      --agent (no docker-image) → HostCLIAgent (host process)
      --model (no --agent)      → LLMAgent (non-agentic API call)
      (nothing)                 → GoldenAgent (reference patches)
    """
    from eval.runner import GoldenAgent

    # Env vars to pass through to agents
    agent_env = {}
    if args.model:
        agent_env["CVDP_MODEL"] = args.model
    if args.api_key:
        agent_env["CVDP_API_KEY"] = args.api_key
    if args.base_url:
        agent_env["CVDP_BASE_URL"] = args.base_url

    if args.agent and args.docker_image:
        from eval.agents.docker_agent import DockerAgent
        return DockerAgent(
            image=args.docker_image,
            timeout=args.timeout,
            env=agent_env,
            network_name=args.network_name,
        )

    if args.agent:
        from eval.agents.host_cli import HostCLIAgent
        return HostCLIAgent(
            command=args.agent,
            timeout=args.timeout,
            env=agent_env,
        )

    if args.model:
        from eval.agents.llm_agent import LLMAgent
        return LLMAgent(
            model_name=args.model,
            custom_factory_path=args.custom_factory,
            api_key=args.api_key,
            base_url=args.base_url,
            timeout=args.timeout,
        )

    # No agent, no model → golden mode
    print("No --agent or --model specified, running in golden mode (reference patches)")
    return GoldenAgent()


def _save_incremental(results: dict, path: str):
    """Save intermediate results to JSON (called after each datapoint)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w") as f:
        json.dump(results, f, indent=2)


def _generate_report(raw_path: str, prefix: str):
    """Generate report from raw results JSON."""
    from src.report import auto_generate_text_report

    report_json = os.path.join(prefix, "report.json")

    # Copy raw results as report input
    if os.path.exists(raw_path):
        with open(raw_path) as f:
            data = json.load(f)
        with open(report_json, "w") as f:
            json.dump(data, f, indent=2)
        auto_generate_text_report(report_json)


def main():
    args = parse_args()

    # Regenerate report from existing results
    if args.regenerate_report:
        raw_path = os.path.join(args.prefix, "raw_result.json")
        if not os.path.exists(raw_path):
            print(f"Error: {raw_path} not found")
            sys.exit(1)
        _generate_report(raw_path, args.prefix)
        return

    agent = build_agent(args)

    from eval.runner import BenchmarkRunner
    runner = BenchmarkRunner(
        dataset_path=args.filename,
        agent=agent,
        prefix=args.prefix,
        threads=args.threads,
        network_name=args.network_name,
    )

    # Run single or all
    if args.id:
        if args.id not in runner.datapoints:
            print(f"Error: datapoint '{args.id}' not found in dataset")
            sys.exit(1)
        results = {args.id: runner.run_single(args.id)}
    else:
        results = runner.run_all()

    # Save and report
    raw_path = os.path.join(args.prefix, "raw_result.json")
    runner.save_results(results, raw_path)
    _generate_report(raw_path, args.prefix)

    print(f"Done. Results in {args.prefix}/")


if __name__ == "__main__":
    main()
