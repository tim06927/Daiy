"""Extended test to diagnose why models aren't counting gears in images.

This adds a direct gear-counting test to see if the models can actually
see and count the cogs in the cassette image.
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


def load_image_base64() -> str:
    """Load and encode the test image."""
    with open(IMAGE_PATH, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def test_direct_count(model_name: str, image_base64: str) -> dict:
    """Ask the model to directly count cogs in the image."""
    print(f"\n{'='*60}")
    print(f"DIRECT COG COUNT TEST: {model_name}")
    print(f"{'='*60}")
    
    prompt = """Look at this image of a bike cassette/gears. 

Please count the number of individual cogs (sprockets) you can see on the cassette.

Also identify:
1. What type of bike this appears to be (road, MTB, gravel, etc.)
2. Any brand or component group you can identify

Respond with JSON:
{
  "cog_count": <number>,
  "bike_type": "<type>",
  "brand_or_group": "<if visible>",
  "confidence": "<high/medium/low>",
  "notes": "<any observations>"
}"""
    
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
            # Try to extract JSON from response
            try:
                # Handle case where response has markdown code blocks
                if "```json" in raw_response:
                    json_str = raw_response.split("```json")[1].split("```")[0]
                elif "```" in raw_response:
                    json_str = raw_response.split("```")[1].split("```")[0]
                else:
                    json_str = raw_response
                
                parsed = json.loads(json_str.strip())
                print(f"\nParsed result:")
                print(json.dumps(parsed, indent=2))
                return {"model": model_name, "success": True, **parsed}
            except (json.JSONDecodeError, IndexError) as e:
                print(f"\nCouldn't parse JSON: {e}")
                return {"model": model_name, "success": False, "raw": raw_response}
    except Exception as e:
        print(f"\nAPI error: {e}")
        return {"model": model_name, "success": False, "error": str(e)}


def test_clarification_with_image_emphasis(model_name: str, image_base64: str) -> dict:
    """Test with a prompt that explicitly asks to analyze the image."""
    print(f"\n{'='*60}")
    print(f"IMAGE-EMPHASIS CLARIFICATION TEST: {model_name}")
    print(f"{'='*60}")
    
    # Modified prompt that explicitly mentions image analysis
    prompt = """You are assisting a bike components recommender. The user wrote:
"Need a new cassette"

The user has also uploaded a PHOTO of their current bike/cassette.

YOUR TASK: 
1. CAREFULLY ANALYZE THE UPLOADED IMAGE to count the cogs and identify the bike type
2. Use this visual information to infer the drivetrain speed and use case
3. Only ask for clarification if you truly cannot determine from the image

Respond with pure JSON ONLY:
{
  "inferred_speed": <int or null>,
  "inferred_use_case": "<string or null>",
  "speed_options": [],
  "use_case_options": [],
  "image_analysis": "<what you see in the image>"
}

IMPORTANT: Count the cogs in the cassette image to determine the speed. 
For example: 10 cogs = 10-speed, 11 cogs = 11-speed, 12 cogs = 12-speed."""
    
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
                print(f"\nParsed result:")
                print(json.dumps(parsed, indent=2))
                return {"model": model_name, "success": True, **parsed}
            except json.JSONDecodeError as e:
                print(f"\nJSON parse error: {e}")
                return {"model": model_name, "success": False, "raw": raw_response}
    except Exception as e:
        print(f"\nAPI error: {e}")
        return {"model": model_name, "success": False, "error": str(e)}


def main():
    """Run diagnostic tests."""
    print("Loading test image...")
    image_base64 = load_image_base64()
    print(f"Image loaded: {len(image_base64)} base64 characters")
    print(f"Image path: {IMAGE_PATH}")
    
    models = ["gpt-5-mini", "gpt-5.2"]
    
    print("\n" + "#"*60)
    print("TEST 1: Direct Cog Counting")
    print("#"*60)
    
    count_results = []
    for model in models:
        result = test_direct_count(model, image_base64)
        count_results.append(result)
    
    print("\n" + "#"*60)
    print("TEST 2: Clarification with Image Emphasis")
    print("#"*60)
    
    clarify_results = []
    for model in models:
        result = test_clarification_with_image_emphasis(model, image_base64)
        clarify_results.append(result)
    
    # Summary
    print("\n" + "="*60)
    print("FINAL SUMMARY")
    print("="*60)
    
    print("\nDirect Cog Count Results:")
    for r in count_results:
        cogs = r.get("cog_count", "N/A")
        bike = r.get("bike_type", "N/A")
        conf = r.get("confidence", "N/A")
        print(f"  {r['model']}: {cogs} cogs, {bike}, confidence: {conf}")
    
    print("\nImage-Emphasis Clarification Results:")
    for r in clarify_results:
        speed = r.get("inferred_speed", "N/A")
        use = r.get("inferred_use_case", "N/A")
        analysis = r.get("image_analysis", "N/A")[:80] + "..." if r.get("image_analysis") else "N/A"
        print(f"  {r['model']}: speed={speed}, use={use}")
        print(f"    Analysis: {analysis}")
    
    print("\n" + "="*60)
    print("RECOMMENDATION")
    print("="*60)
    
    # Check if emphasis helps
    for r in clarify_results:
        if r.get("inferred_speed"):
            print(f"\n✓ {r['model']} inferred speed when prompted to analyze image!")
            print("  → The current prompt may not emphasize image analysis enough")


if __name__ == "__main__":
    main()
