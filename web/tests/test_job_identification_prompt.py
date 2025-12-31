"""Tests for the job identification prompt wording to avoid duplicate clarifications."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from job_identification import _build_job_identification_prompt  # type: ignore


def test_prompt_mentions_deduplication_rules():
    prompt = _build_job_identification_prompt("need a cassette", image_attached=False)

    assert "Do NOT include multiple variations of the same spec" in prompt
    assert "Do NOT ask implied specs twice" in prompt
