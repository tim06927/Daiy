"""CLI demo of grounded AI recommendations for bike component upgrades.

This module demonstrates how to use real product data (grounding) to prevent
LLM hallucination. The LLM can only recommend products actually in our inventory,
ensuring practical and actionable advice.

The demo loads a product catalog, builds a grounding context (the real products),
and asks the LLM to pick a cassette and chain upgrade based on the available
inventory.
"""

import json

from dotenv import load_dotenv
from openai import OpenAI

from catalog import build_grounding_context, load_catalog

load_dotenv()  # Load environment variables from .env file

# Uses OPENAI_API_KEY from your environment
client = OpenAI()


def make_prompt(context: dict) -> str:
    """Build a prompt instructing the LLM to make a grounded recommendation.

    Creates a detailed prompt that:
    - Establishes the LLM's role (experienced bike mechanic)
    - Provides the grounding context (real products only, in JSON format)
    - Explicitly forbids inventing products or URLs
    - Requests a reasoned choice with explanation
    - Asks for machine-readable output (JSON) for programmatic parsing

    Args:
        context: Dict from build_grounding_context() with candidates and project info.

    Returns:
        Formatted prompt string ready for LLM submission.
    """
    return f"""
You are an experienced bike mechanic.

A user wants to upgrade their cassette.

Here is the project and the available products from ONE shop.
You MUST ONLY recommend products from the lists below.
Do NOT invent other products or URLs.

CONTEXT (JSON):
{json.dumps(context, indent=2)}

TASK:
1. Choose ONE cassette and ONE matching chain from the candidates.
2. Explain in 3–5 bullet points why they fit the user's bike and project.
   - cover speed compatibility
   - cover use case (road / gravel / MTB)
   - cover gear range (why this is better for climbing).
3. Output at the end a short machine-readable summary in JSON with this shape:

{{
  "cassette_url": "...",
  "chain_url": "...",
  "notes": ["...", "..."]
}}

Answer in English.
""".strip()


def call_llm(prompt: str) -> str:
    """Call OpenAI gpt-5-nano with extended thinking (Responses API).

    Submits the prompt to the LLM and extracts the text response. The Responses API
    may return multiple output items (reasoning blocks followed by the actual message).
    This function filters for the first item with actual content, skipping reasoning-only
    items.

    Args:
        prompt: The prompt to send to the LLM.

    Returns:
        The text response from the LLM (excluding reasoning blocks).

    Raises:
        ValueError: If the response contains no content.
    """
    resp = client.responses.create(
        model="gpt-5-nano",  # change to another text model if you like
        input=prompt,
    )
    # extract text (Responses API format)
    # The response contains a reasoning item first, then the actual message
    # Find the message with content (not the reasoning item)
    for item in resp.output:
        if hasattr(item, "content") and item.content is not None:
            return item.content[0].text  # type: ignore[union-attr]

    # Fallback: if no content found, raise an error
    raise ValueError("No content found in response")


def run_demo() -> None:
    """Execute the full grounded recommendation workflow.

    Loads the product catalog, builds a grounding context with the user's project,
    generates a prompt, calls the LLM, and prints both the prompt and the response.
    """
    df = load_catalog()
    context = build_grounding_context(df)
    prompt = make_prompt(context)

    print("=== PROMPT ===")
    print(prompt)
    print("\n=== RESPONSE ===")
    answer = call_llm(prompt)
    print(answer)


if __name__ == "__main__":
    run_demo()
