"""
Integration check for the vision-capable Responses API using a real bike photo.

Requirements:
- Set OPENAI_API_KEY in the environment.
- Keep data/grizl 7 drivetrain.jpeg present (added by user).

Run as a script (no pytest needed):
    python web/tests/test_vision_flow.py

Or with pytest (if installed):
    pytest web/tests/test_vision_flow.py -q
"""

import base64
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv


def _load_image_b64(img_path: Path) -> str:
    data = img_path.read_bytes()
    return base64.b64encode(data).decode("utf-8")


def run_vision_flow() -> dict:
    repo_root = Path(__file__).resolve().parents[2]

    # Load .env so OPENAI_API_KEY is available when running as a standalone script.
    load_dotenv(dotenv_path=repo_root / ".env")
    # Ensure repo root is on sys.path for imports (config, web).
    web_dir = repo_root / "web"
    for p in (repo_root, web_dir):
        p_str = str(p)
        if p_str not in sys.path:
            sys.path.insert(0, p_str)

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key or api_key == "your-api-key-here":
        raise SystemExit("OPENAI_API_KEY is required to run this test.")

    # Import inside the function so missing API keys can short-circuit before module import.
    from web import app as app_module

    img_path = repo_root / "data" / "grizl_7_drivetrain.jpeg"
    if not img_path.exists():
        raise SystemExit(f"Test image missing at {img_path}")

    img_b64 = _load_image_b64(img_path)

    problem_text = (
        "I ride an 11-speed gravel bike with Shimano GRX. "
        "I want easier climbing gears without losing too much on flats."
    )

    context = app_module.build_grounding_context(
        problem_text=problem_text,
        bike_speed=11,
        use_case="gravel",
        image_base64=img_b64,
    )
    prompt = app_module.make_prompt(context, image_attached=True)
    result = app_module.call_llm(
        prompt,
        image_base64=img_b64,
        image_meta={"source": "vision_flow_test"},
    )

    sections = result.get("sections") or {}
    ranking = result.get("product_ranking") or {}

    assert isinstance(sections, dict) and sections, "Missing sections block"
    assert isinstance(ranking, dict) and ranking, "Missing product_ranking block"
    assert sections.get("why_it_fits"), "why_it_fits should not be empty"
    assert sections.get("suggested_workflow"), "suggested_workflow should not be empty"
    assert sections.get("checklist"), "checklist should not be empty"
    assert "cassettes" in ranking and ranking["cassettes"].get("best_index") is not None
    assert "chains" in ranking and ranking["chains"].get("best_index") is not None

    log_payload = {
        "problem_text": problem_text,
        "image_path": str(img_path),
        "sections": sections,
        "product_ranking": ranking,
    }

    log_path = repo_root / "logs" / "vision_flow_test_result.json"
    log_path.parent.mkdir(exist_ok=True)
    log_path.write_text(json.dumps(log_payload, indent=2), encoding="utf-8")

    return log_payload


def test_vision_flow():
    run_vision_flow()


if __name__ == "__main__":
    payload = run_vision_flow()
    print("Vision flow test completed. Result saved to logs/vision_flow_test_result.json")
