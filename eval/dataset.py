"""Unified dataset loading and normalization for CVDP benchmark.

Normalizes both agentic and copilot JSONL formats into a common Datapoint
dataclass so downstream code doesn't need to care about format differences.
"""

import json
import os
from dataclasses import dataclass, field

from src.constants import CODE_COMPREHENSION_CATEGORIES


@dataclass
class Datapoint:
    id: str
    categories: list
    prompt: str
    context_files: dict  # {filepath: content} — initial codebase
    expected_patches: dict  # {filepath: content} — golden solution
    harness: dict  # test harness config
    system_message: str | None = None
    subjective_reference: str | None = None  # reference answer for comprehension
    is_agentic: bool = False
    is_comprehension: bool = False
    category_id: int = 0
    difficulty: str = "medium"
    raw: dict = field(default_factory=dict, repr=False)


def _parse_category_id(categories: list) -> int:
    if categories and isinstance(categories[0], str) and categories[0].startswith("cid"):
        return int(categories[0][3:])
    return 0


def _parse_agentic(raw: dict) -> Datapoint:
    cat_id = _parse_category_id(raw.get("categories", []))
    return Datapoint(
        id=raw["id"],
        categories=raw.get("categories", []),
        prompt=raw.get("prompt", ""),
        context_files=raw.get("context", {}),
        expected_patches=raw.get("patch", {}),
        harness=raw.get("harness", {}),
        system_message=raw.get("system_message"),
        subjective_reference=raw.get("subjective_reference"),
        is_agentic=True,
        is_comprehension=cat_id in CODE_COMPREHENSION_CATEGORIES,
        category_id=cat_id,
        difficulty=raw.get("categories", ["", "medium"])[1] if len(raw.get("categories", [])) > 1 else "medium",
        raw=raw,
    )


def _parse_copilot(raw: dict) -> Datapoint:
    cat_id = _parse_category_id(raw.get("categories", []))
    inp = raw.get("input", {})
    out = raw.get("output", {})

    # Subjective reference for comprehension tasks
    subj_ref = raw.get("subjective_reference") or out.get("response")

    return Datapoint(
        id=raw["id"],
        categories=raw.get("categories", []),
        prompt=inp.get("prompt", ""),
        context_files=inp.get("context", {}),
        expected_patches=out.get("context", {}),
        harness=raw.get("harness", {}),
        system_message=None,
        subjective_reference=subj_ref,
        is_agentic=False,
        is_comprehension=cat_id in CODE_COMPREHENSION_CATEGORIES,
        category_id=cat_id,
        difficulty=raw.get("categories", ["", "medium"])[1] if len(raw.get("categories", [])) > 1 else "medium",
        raw=raw,
    )


def detect_format(raw: dict) -> bool:
    """Return True if the datapoint is agentic format."""
    dp_id = raw.get("id", "")
    return "_agentic_" in dp_id


def load_dataset(filename: str) -> dict[str, Datapoint]:
    """Load a JSONL dataset file and return {id: Datapoint} dict."""
    datapoints = {}
    with open(filename, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            raw = json.loads(line)
            if detect_format(raw):
                dp = _parse_agentic(raw)
            else:
                dp = _parse_copilot(raw)
            datapoints[dp.id] = dp
    return datapoints
