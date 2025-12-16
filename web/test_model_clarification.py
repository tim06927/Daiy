"""Test script to investigate why gpt-5.2 doesn't infer speed/use_case from images.

This compares the behavior of gpt-5-mini vs gpt-5.2 when given the same image
to see why gpt-5.2 consistently fails to infer drivetrain speed and use case.
"""

import base64
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# Load environment variables
env_path = Path(__file__).parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

client = OpenAI()

# Test image path
IMAGE_PATH = Path(__file__).parent.parent / "data" / "grizl_gears.jpeg"

# The prompt used in app.py for clarification (updated with image analysis emphasis)
def get_clarification_prompt(has_image: bool) -> str:
    """Build the clarification prompt, with image analysis instructions if image attached."""
    image_instruction = ""
    if has_image:
        image_instruction = (
            "\n\nIMPORTANT - IMAGE ANALYSIS:\n"
            "The user has uploaded a PHOTO. Carefully analyze the image to:\n"
            "- COUNT the number of cogs/sprockets on the cassette to determine speed "
            "(e.g., 10 cogs = 10-speed, 11 cogs = 11-speed, 12 cogs = 12-speed)\n"
            "- IDENTIFY the bike type from visual cues (drop bars = road/gravel, flat bars = MTB, etc.)\n"
            "- Look for brand logos or component markings\n"
            "Use this visual information to infer speed and use_case. "
            "Only ask for clarification if the image is unclear or doesn't show relevant components.\n"
        )
    
    return f"""You are assisting a bike components recommender. The user wrote:
"Need a new cassette"

The regex-based system could not automatically detect: drivetrain_speed, use_case.
{image_instruction}
YOUR TASK: Carefully analyze the user's text (and image if provided) and either:
1. INFER the missing values if they are clearly stated, strongly implied, or visible in the image, OR
2. PROPOSE option lists if the information is truly ambiguous or absent.

Respond with pure JSON ONLY (no prose), using this exact structure:
{{
  "inferred_speed": 11,  // int if you can infer, null if you cannot
  "inferred_use_case": "road",  // lowercase string if you can infer, null if you cannot
  "speed_options": [],  // empty if inferred, else ["8-speed", "11-speed", "12-speed"]
  "use_case_options": []  // empty if inferred, else ["road", "gravel", "mtb"]
}}

RULES:
- If you can determine the speed/use_case from context or the image, set inferred_* and leave options empty
- Only populate options lists if you genuinely cannot infer the value
- For speed: count cogs in image, or look for mentions like '12-speed', 'shimano 105' (11-speed), etc.
- For use_case: look at bike frame/handlebars in image, or text mentions of bike types, terrain, riding style
- Keep option lists to max 5 items with short labels
- Use lowercase for use_case values: 'road', 'gravel', 'mtb', 'commute', 'touring', etc.
"""


def load_image_base64() -> str:
    """Load and encode the test image."""
    with open(IMAGE_PATH, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def test_model(model_name: str, image_base64: str) -> dict:
    """Test a specific model's response to the clarification prompt with image."""
    print(f"\n{'='*60}")
    print(f"Testing model: {model_name}")
    print(f"{'='*60}")
    
    prompt = get_clarification_prompt(has_image=True)
    
    input_payload = [
        {"role": "user", "content": [{"type": "input_text", "text": prompt}]},
        {
            "role": "user",
            "content": [
                {
                    "type": "input_image",
                    "image_url": f"data:image/jpeg;base64,{image_base64}",
                }
            ],
        },
    ]
    
    print(f"\nSending request to {model_name}...")
    
    try:
        resp = client.responses.create(
            model=model_name,
            input=input_payload,
        )
        
        raw_response = None
        for item in resp.output:
            if hasattr(item, "content") and item.content is not None:
                raw_response = item.content[0].text
                break
        
        print(f"\nRaw response:\n{raw_response}")
        
        if raw_response:
            try:
                parsed = json.loads(raw_response)
                print(f"\nParsed JSON:")
                print(json.dumps(parsed, indent=2))
                return {
                    "model": model_name,
                    "success": True,
                    "inferred_speed": parsed.get("inferred_speed"),
                    "inferred_use_case": parsed.get("inferred_use_case"),
                    "speed_options": parsed.get("speed_options", []),
                    "use_case_options": parsed.get("use_case_options", []),
                    "raw": raw_response,
                }
            except json.JSONDecodeError as e:
                print(f"\nJSON parse error: {e}")
                return {
                    "model": model_name,
                    "success": False,
                    "error": f"JSON parse error: {e}",
                    "raw": raw_response,
                }
    except Exception as e:
        print(f"\nAPI error: {e}")
        return {
            "model": model_name,
            "success": False,
            "error": str(e),
            "raw": None,
        }


def main():
    """Run comparison tests between models."""
    print("Loading test image...")
    image_base64 = load_image_base64()
    print(f"Image loaded: {len(image_base64)} base64 characters")
    
    models = ["gpt-5-mini", "gpt-5.2"]
    results = []
    
    for model in models:
        result = test_model(model, image_base64)
        results.append(result)
    
    # Summary comparison
    print("\n" + "="*60)
    print("SUMMARY COMPARISON")
    print("="*60)
    print(f"{'Model':<15} {'Inferred Speed':<20} {'Inferred Use Case':<20}")
    print("-"*60)
    for r in results:
        speed = r.get("inferred_speed", "ERROR")
        use_case = r.get("inferred_use_case", "ERROR")
        speed_opts = r.get("speed_options", [])
        use_opts = r.get("use_case_options", [])
        
        speed_str = str(speed) if speed else f"None (opts: {speed_opts})"
        use_str = str(use_case) if use_case else f"None (opts: {use_opts})"
        
        print(f"{r['model']:<15} {speed_str:<20} {use_str:<20}")
    
    print("\n" + "="*60)
    print("ANALYSIS")
    print("="*60)
    
    # Check if gpt-5.2 is returning options instead of inferences
    gpt5_mini = results[0] if results[0]["model"] == "gpt-5-mini" else results[1]
    gpt52 = results[1] if results[1]["model"] == "gpt-5.2" else results[0]
    
    if gpt5_mini.get("success") and gpt52.get("success"):
        mini_infers = bool(gpt5_mini.get("inferred_speed") or gpt5_mini.get("inferred_use_case"))
        gpt52_infers = bool(gpt52.get("inferred_speed") or gpt52.get("inferred_use_case"))
        
        if mini_infers and not gpt52_infers:
            print("FINDING: gpt-5-mini infers values, gpt-5.2 does not.")
            print("\nPossible causes:")
            print("1. gpt-5.2 may be more conservative about inferring from images")
            print("2. gpt-5.2 may interpret the prompt more literally")
            print("3. Different vision capabilities between models")
            print("\nSuggested fixes:")
            print("- Add explicit instruction to count cogs in the image")
            print("- Make the prompt more explicit about using image analysis")
            print("- Lower the threshold for inference (be more confident)")
        elif not mini_infers and not gpt52_infers:
            print("FINDING: Neither model infers values - may be an image issue")
        elif mini_infers and gpt52_infers:
            print("FINDING: Both models infer values correctly")
        else:
            print("FINDING: gpt-5.2 infers but gpt-5-mini does not (unexpected)")


if __name__ == "__main__":
    main()
