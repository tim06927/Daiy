
import json

from openai import OpenAI  # pip install openai
from catalog import load_catalog, build_grounding_context


# Uses OPENAI_API_KEY from your environment
client = OpenAI()


def make_prompt(context: dict) -> str:
    """
    Build a single prompt that:
    - gives the LLM the grounded context (only real products)
    - asks it to pick a cassette + chain and explain why
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
    """
    Call the LLM using the OpenAI Responses API.
    Adapt 'model' to whatever you have access to.
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
            return item.content[0].text
    
    # Fallback: if no content found, raise an error
    raise ValueError("No content found in response")


def run_demo():
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
