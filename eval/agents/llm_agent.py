"""LLM API agent adapter for non-agentic (copilot) mode.

Builds a prompt from the datapoint context, calls the LLM API,
parses the response into file modifications.
"""

import json
import logging
import os

from eval.agents.base import AgentAdapter, AgentResult, WorkspaceInfo
from eval.dataset import Datapoint

from src.constants import CODE_COMPREHENSION_CATEGORIES
from src.llm_lib.model_factory import ModelFactory, load_custom_factory
from src.model_helpers import ModelHelpers
from src.config_manager import config


class LLMAgent(AgentAdapter):
    """Adapter that calls an LLM API to generate code (non-agentic mode).

    Supports any OpenAI-compatible API via --api-key and --base-url flags.
    """

    def __init__(self, model_name: str, custom_factory_path: str = None,
                 api_key: str = None, base_url: str = None, timeout: int = None):
        self.model_name = model_name
        self.api_key = api_key
        self.base_url = base_url
        self.timeout = timeout or config.get("MODEL_TIMEOUT")
        self.retry_count = config.get("LLM_RETRY_COUNT", 3)

        # If base_url is provided, we create a generic OpenAI-compatible instance
        # instead of going through the factory routing
        if base_url:
            self.factory = None
        else:
            factory = load_custom_factory(custom_factory_path)
            self.factory = factory if factory else ModelFactory()

        self.helpers = ModelHelpers()
        self.folders = self.helpers.folders

    def _create_model(self):
        """Create the model instance, handling direct API config or factory routing."""
        if self.base_url:
            # Direct OpenAI-compatible API — bypass factory
            import openai
            from src.llm_lib.openai_llm import OpenAI_Instance

            key = self.api_key or config.get("OPENAI_USER_KEY")
            if not key:
                raise ValueError("--api-key is required when using --base-url")

            instance = OpenAI_Instance.__new__(OpenAI_Instance)
            instance.context = self.folders
            instance.model = self.model_name
            instance.debug = False
            instance.chat = openai.OpenAI(api_key=key, base_url=self.base_url)
            instance.set_debug(False)
            return instance

        return self.factory.create_model(
            model_name=self.model_name,
            context=self.folders,
            key=self.api_key,
        )

    def execute(self, workspace: WorkspaceInfo, dp: Datapoint) -> AgentResult:
        model = self._create_model()

        # Build prompt from context files
        prompt = ""
        for filepath, content in dp.context_files.items():
            prompt += f"\nConsider the following content for the file {filepath}:\n```\n{content}\n```"
        prompt += f"\nProvide me one answer for this request: {dp.prompt}\n"

        # Determine expected output files
        files = list(dp.expected_patches.keys())
        is_comprehension = dp.category_id in CODE_COMPREHENSION_CATEGORIES

        if is_comprehension:
            files = []

        # Add file instructions
        schema_to_use, no_schema = self.helpers.determine_schema(files)
        if len(files) == 1:
            prompt += f"Please provide your response as plain text without any JSON formatting. Your response will be saved directly to: {files[0]}.\n"
        elif len(files) > 1:
            prompt += f"Name the files as: {files}.\n"
        elif is_comprehension:
            prompt += 'Provide your response using the format: { "response": "<your answer here>" }\n'
        else:
            prompt += "Provide your response below.\n"

        # Save prompt log
        prompts_dir = os.path.join(workspace.repo_path, "prompts")
        os.makedirs(prompts_dir, exist_ok=True)
        logfile = os.path.join(prompts_dir, f"{workspace.issue_id}.md")

        # Call LLM with retries
        retries = self.retry_count
        output = {}
        while True:
            try:
                output, success = model.prompt(
                    prompt,
                    schema=schema_to_use,
                    prompt_log=logfile,
                    files=files,
                    timeout=self.timeout,
                    category=dp.category_id,
                )
                if success:
                    break
                if retries > 0:
                    retries -= 1
                    print(f"Retrying LLM API for {dp.id}...")
                else:
                    logging.error(f"Failed to parse response after retries for {dp.id}")
                    output = {}
                    break
            except Exception as e:
                if retries > 0:
                    retries -= 1
                    print(f"Exception calling LLM for {dp.id}: {e}. Retrying...")
                else:
                    return AgentResult(success=False, error=str(e), log_file=logfile)

        # Parse output into modified files
        modified = self._parse_output(output, files, is_comprehension)
        return AgentResult(success=True, modified_files=modified, log_file=logfile)

    def _parse_output(self, output: dict, files: list, is_comprehension: bool) -> dict:
        """Convert LLM output dict into {filepath: content} modifications."""
        result = {}

        if len(files) == 1 and "direct_text" in output:
            result[files[0]] = output["direct_text"]
        elif len(files) == 1 and "response" in output:
            result[files[0]] = output["response"]
        elif "code" in output:
            for entry in output["code"]:
                for filename, code in entry.items():
                    result[filename] = code
        else:
            # Fallback — put response in subjective.txt
            if "direct_text" in output:
                result["subjective.txt"] = output["direct_text"]
            elif "response" in output:
                result["subjective.txt"] = output["response"]
            elif output:
                result["subjective.txt"] = str(output)

        return result
