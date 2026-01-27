# SPDX-FileCopyrightText: Copyright (c) 2025 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0

"""
Custom model factory for OpenRouter and DeepSeek API integration.

Usage:
    # Set your API key in .env file or environment:
    # OPENROUTER_API_KEY=your_key_here
    # DEEPSEEK_API_KEY=your_key_here

    # Run with DeepSeek:
    python run_benchmark.py -f input.json -l -m deepseek-chat --custom-factory ./openrouter_deepseek_factory.py

    # Run with OpenRouter (any model):
    python run_benchmark.py -f input.json -l -m openai/gpt-4o --custom-factory ./openrouter_deepseek_factory.py

Supported model prefixes:
    - deepseek-*: Uses DeepSeek API (e.g., deepseek-chat, deepseek-coder)
    - openrouter/*: Uses OpenRouter API (e.g., openrouter/anthropic/claude-3-opus)
    - Any other model starting with known providers will use OpenRouter
"""

import openai
import logging
import os
from typing import Optional, Any

from src.llm_lib.model_factory import ModelFactory
from src.llm_lib.openai_llm import OpenAI_Instance
from src.llm_lib.subjective_score_model import SubjectiveScoreModel_Instance
from src.config_manager import config

logging.basicConfig(level=logging.INFO)


class DeepSeekInstance(OpenAI_Instance):
    """
    DeepSeek API instance using OpenAI-compatible interface.

    DeepSeek API endpoint: https://api.deepseek.com
    """

    def __init__(self, context: str = "You are a helpful assistant.",
                 key: Optional[str] = None, model: str = "deepseek-chat"):
        self.context = context
        self.model = model
        self.debug = False

        # Get API key from parameter, env var, or config
        api_key = key or os.environ.get("DEEPSEEK_API_KEY") or config.get("DEEPSEEK_API_KEY")

        if not api_key:
            raise ValueError(
                "DeepSeek API key not found. Please set DEEPSEEK_API_KEY in your .env file "
                "or environment variable."
            )

        # Initialize OpenAI client with DeepSeek base URL
        self.chat = openai.OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )

        logging.info(f"Created DeepSeek Model instance. Using model: {self.model}")
        self.set_debug(False)


class OpenRouterInstance(OpenAI_Instance):
    """
    OpenRouter API instance using OpenAI-compatible interface.

    OpenRouter API endpoint: https://openrouter.ai/api/v1

    OpenRouter supports many models including:
    - openai/gpt-4o, openai/gpt-4-turbo
    - anthropic/claude-3-opus, anthropic/claude-3-sonnet
    - google/gemini-pro, google/gemini-pro-vision
    - meta-llama/llama-3-70b-instruct
    - And many more: https://openrouter.ai/models
    """

    def __init__(self, context: str = "You are a helpful assistant.",
                 key: Optional[str] = None, model: str = "openai/gpt-4o"):
        self.context = context
        self.model = model
        self.debug = False

        # Get API key from parameter, env var, or config
        api_key = key or os.environ.get("OPENROUTER_API_KEY") or config.get("OPENROUTER_API_KEY")

        if not api_key:
            raise ValueError(
                "OpenRouter API key not found. Please set OPENROUTER_API_KEY in your .env file "
                "or environment variable."
            )

        # Initialize OpenAI client with OpenRouter base URL
        self.chat = openai.OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://github.com/NVlabs/cvdp-benchmark",
                "X-Title": "CVDP Benchmark"
            }
        )

        logging.info(f"Created OpenRouter Model instance. Using model: {self.model}")
        self.set_debug(False)


class DeepSeekSubjectiveScoreModel(SubjectiveScoreModel_Instance):
    """
    Subjective scoring model using DeepSeek API.

    This overrides the default OpenAI-based subjective scoring to use DeepSeek instead.
    """

    def __init__(self, context: Any = None, key: Optional[str] = None, model: str = None):
        if model is None or model == "sbj_score":
            model = "deepseek-chat"
        self.model = model
        self.debug = False

        # Get API key from parameter, env var, or config
        api_key = key or os.environ.get("DEEPSEEK_API_KEY") or config.get("DEEPSEEK_API_KEY")

        if not api_key:
            raise ValueError(
                "DeepSeek API key not found for subjective scoring. "
                "Please set DEEPSEEK_API_KEY in your .env file or environment variable."
            )

        # Initialize OpenAI client with DeepSeek base URL
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url="https://api.deepseek.com"
        )

        logging.info(f"Created DeepSeek Subjective Scoring Model. Using model: {self.model}")


class OpenRouterSubjectiveScoreModel(SubjectiveScoreModel_Instance):
    """
    Subjective scoring model using OpenRouter API.

    This overrides the default OpenAI-based subjective scoring to use OpenRouter instead.
    """

    def __init__(self, context: Any = None, key: Optional[str] = None, model: str = None):
        if model is None or model == "sbj_score":
            model = "openai/gpt-4o-mini"  # Default to a cost-effective model for scoring
        self.model = model
        self.debug = False

        # Get API key from parameter, env var, or config
        api_key = key or os.environ.get("OPENROUTER_API_KEY") or config.get("OPENROUTER_API_KEY")

        if not api_key:
            raise ValueError(
                "OpenRouter API key not found for subjective scoring. "
                "Please set OPENROUTER_API_KEY in your .env file or environment variable."
            )

        # Initialize OpenAI client with OpenRouter base URL
        self.client = openai.OpenAI(
            api_key=api_key,
            base_url="https://openrouter.ai/api/v1",
            default_headers={
                "HTTP-Referer": "https://github.com/NVlabs/cvdp-benchmark",
                "X-Title": "CVDP Benchmark"
            }
        )

        logging.info(f"Created OpenRouter Subjective Scoring Model. Using model: {self.model}")


class CustomModelFactory(ModelFactory):
    """
    Custom model factory that adds support for DeepSeek and OpenRouter APIs.

    Model routing:
    - Models starting with "deepseek" -> DeepSeek API
    - Models starting with "openrouter/" -> OpenRouter API (prefix stripped)
    - Models containing "/" (e.g., "anthropic/claude-3") -> OpenRouter API
    - "sbj_score" -> DeepSeek-based subjective scoring (or OpenRouter if DEEPSEEK_API_KEY not set)
    """

    def __init__(self):
        super().__init__()

        # Register DeepSeek models
        self.model_types["deepseek"] = self._create_deepseek_instance
        self.model_types["deepseek-chat"] = self._create_deepseek_instance
        self.model_types["deepseek-coder"] = self._create_deepseek_instance
        self.model_types["deepseek-reasoner"] = self._create_deepseek_instance

        # Register OpenRouter as a catch-all for provider/model format
        self.model_types["openrouter"] = self._create_openrouter_instance

        # Override sbj_score to use DeepSeek or OpenRouter
        self.model_types["sbj_score"] = self._create_subjective_score_instance

        logging.info("Custom model factory initialized with DeepSeek and OpenRouter support")

    def _create_deepseek_instance(self, model_name: str, context: Any,
                                   key: Optional[str], **kwargs) -> DeepSeekInstance:
        """Create a DeepSeek model instance."""
        return DeepSeekInstance(context=context, key=key, model=model_name)

    def _create_openrouter_instance(self, model_name: str, context: Any,
                                     key: Optional[str], **kwargs) -> OpenRouterInstance:
        """Create an OpenRouter model instance."""
        # Strip "openrouter/" prefix if present
        if model_name.startswith("openrouter/"):
            model_name = model_name[len("openrouter/"):]
        return OpenRouterInstance(context=context, key=key, model=model_name)

    def _create_subjective_score_instance(self, model_name: str, context: Any,
                                           key: Optional[str], **kwargs) -> Any:
        """Create a subjective scoring model instance using DeepSeek or OpenRouter."""
        # Try DeepSeek first, fall back to OpenRouter
        deepseek_key = os.environ.get("DEEPSEEK_API_KEY") or config.get("DEEPSEEK_API_KEY")
        openrouter_key = os.environ.get("OPENROUTER_API_KEY") or config.get("OPENROUTER_API_KEY")

        if deepseek_key:
            logging.info("Creating subjective scoring model using DeepSeek API")
            return DeepSeekSubjectiveScoreModel(context=context, key=key, model=model_name)
        elif openrouter_key:
            logging.info("Creating subjective scoring model using OpenRouter API")
            return OpenRouterSubjectiveScoreModel(context=context, key=key, model=model_name)
        else:
            raise ValueError(
                "No API key found for subjective scoring. "
                "Please set DEEPSEEK_API_KEY or OPENROUTER_API_KEY in your .env file."
            )

    def create_model(self, model_name: str, context: Any = None,
                     key: Optional[str] = None, **kwargs) -> Any:
        """
        Create a model instance based on the model name.

        Routing logic:
        1. If model_name starts with "deepseek" -> DeepSeek API
        2. If model_name starts with "openrouter/" -> OpenRouter API
        3. If model_name contains "/" (provider/model format) -> OpenRouter API
        4. Otherwise -> Use parent class logic (OpenAI, etc.)
        """
        # Route DeepSeek models
        if model_name.startswith("deepseek"):
            logging.info(f"Routing {model_name} to DeepSeek API")
            return self._create_deepseek_instance(model_name, context, key, **kwargs)

        # Route OpenRouter models (explicit prefix or provider/model format)
        if model_name.startswith("openrouter/") or "/" in model_name:
            logging.info(f"Routing {model_name} to OpenRouter API")
            return self._create_openrouter_instance(model_name, context, key, **kwargs)

        # Fall back to parent class for other models (OpenAI, etc.)
        return super().create_model(model_name, context, key, **kwargs)


# For testing the factory directly
if __name__ == "__main__":
    print("Testing CustomModelFactory...")

    factory = CustomModelFactory()

    # Show registered model types
    print(f"\nRegistered model types: {list(factory.model_types.keys())}")

    # Test model routing (without actually creating instances)
    test_models = [
        "deepseek-chat",
        "deepseek-coder",
        "openrouter/anthropic/claude-3-opus",
        "anthropic/claude-3-sonnet",
        "meta-llama/llama-3-70b-instruct",
        "gpt-4o",  # Should fall back to OpenAI
    ]

    print("\nModel routing test:")
    for model in test_models:
        if model.startswith("deepseek"):
            print(f"  {model} -> DeepSeek API")
        elif "/" in model:
            print(f"  {model} -> OpenRouter API")
        else:
            print(f"  {model} -> OpenAI API (default)")
