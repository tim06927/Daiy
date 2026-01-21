"""Dynamic prompt generation for LLM recommendations.

This module provides category-agnostic prompt building for the recommendation flow:
1. Job identification (in job_identification.py)
2. Final recommendation with product matching
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Handle imports for both direct execution and package import
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).parent))
    from categories import PRODUCT_CATEGORIES, get_category_config
else:
    from .categories import PRODUCT_CATEGORIES, get_category_config

__all__ = [
    "make_recommendation_prompt",
    "build_recommendation_context",
]

logger = logging.getLogger(__name__)


def _format_product_for_prompt(product: Dict[str, Any]) -> str:
    """Format a single product for inclusion in prompt.
    
    Args:
        product: Product dict with name, brand, price, etc.
        
    Returns:
        Formatted product string.
    """
    parts = [f"{product.get('name', 'Unknown')}"]
    
    if product.get('brand'):
        parts.append(f"brand: {product['brand']}")
    if product.get('speed'):
        parts.append(f"speed: {product['speed']}")
    if product.get('application'):
        parts.append(f"application: {product['application']}")
    if product.get('price'):
        parts.append(f"price: {product['price']}")
    
    return " | ".join(parts)


def _format_category_products_json(
    category_key: str,
    products: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Format products for a category as a JSON-serializable dict.
    
    Args:
        category_key: Category key.
        products: List of product dicts.
        
    Returns:
        Dict with category info and products.
    """
    config = get_category_config(category_key)
    display_name = config["display_name"] if config else category_key.replace("_", " ").title()
    
    formatted_products = []
    for idx, p in enumerate(products):
        formatted_products.append({
            "index": idx,
            "name": p.get("name", "Unknown"),
            "brand": p.get("brand"),
            "speed": p.get("speed"),
            "application": p.get("application"),
            "price": p.get("price"),
            "url": p.get("url"),
        })
    
    return {
        "category_key": category_key,
        "display_name": display_name,
        "products": formatted_products,
    }




def build_recommendation_context(
    problem_text: str,
    instructions: List[str],
    clarifications: List[Dict[str, Any]],
    category_products: Dict[str, List[Dict[str, Any]]],
    image_base64: Optional[str] = None,
) -> Dict[str, Any]:
    """Build context for the final recommendation prompt.
    
    Args:
        problem_text: Original user's problem description.
        instructions: Step-by-step instructions from job identification.
        clarifications: List of clarification Q&As with user's answers.
        category_products: Dict mapping category keys to product lists.
        image_base64: Optional base64 image.
        
    Returns:
        Context dict for the recommendation prompt.
    """
    # Format category products as JSON structure
    categories_data = []
    for cat_key, products in category_products.items():
        categories_data.append(_format_category_products_json(cat_key, products))
    
    return {
        "user_request": problem_text,
        "instructions": instructions,
        "clarifications": clarifications,
        "category_products": categories_data,
        "image_base64": image_base64,
    }


def make_recommendation_prompt(
    context: Dict[str, Any],
    image_attached: bool = False,
) -> str:
    """Generate the final recommendation prompt.
    
    Takes the job identification instructions, clarification answers,
    and available products to generate specific product recommendations.
    
    Args:
        context: Context from build_recommendation_context.
        image_attached: Whether user image is attached.
        
    Returns:
        Prompt string for LLM.
    """
    return _make_recommendation_prompt_new(context, image_attached)


def _make_recommendation_prompt_new(
    context: Dict[str, Any],
    image_attached: bool = False,
) -> str:
    """Generate recommendation prompt using new format with instructions.
    
    Args:
        context: Context with instructions, clarifications, and category_products.
        image_attached: Whether user image is attached.
        
    Returns:
        Prompt string for LLM.
    """
    user_text = context.get("user_request", "")
    instructions = context.get("instructions", [])
    clarifications = context.get("clarifications", [])
    category_products = context.get("category_products", [])
    
    # Format instructions
    instructions_text = "\n".join(f"  {i+1}. {step}" for i, step in enumerate(instructions))
    
    # Format clarifications with answers
    clarifications_text = ""
    if clarifications:
        clarif_lines = []
        for c in clarifications:
            spec = c.get("spec_name", "Unknown")
            answer = c.get("answer", "Not provided")
            clarif_lines.append(f"  - {spec}: {answer}")
        clarifications_text = "User-provided specifications:\n" + "\n".join(clarif_lines)
    else:
        clarifications_text = "No additional specifications provided."
    
    # Format available products as JSON
    products_json = json.dumps(category_products, indent=2)
    
    image_note = ""
    if image_attached:
        image_note = """
IMPORTANT - IMAGE REFERENCE:
The user's original photo is attached. Use visual information to verify product fit.
"""
    
    return f"""You are an expert bicycle mechanic finalizing product recommendations.

ORIGINAL USER REQUEST:
\"\"\"{user_text}\"\"\"

PRELIMINARY INSTRUCTIONS (from initial analysis):
{instructions_text}

{clarifications_text}
{image_note}
AVAILABLE PRODUCTS BY CATEGORY:
{products_json}

YOUR TASK:
1. Create a recipe format with INGREDIENTS (specific product names) and STEPS (detailed instructions)
2. Replace all category references with SPECIFIC PRODUCTS from the available products
3. Ensure every ingredient is used in at least one step
4. Ensure every step references only ingredients from the list

RESPONSE FORMAT (return pure JSON only, no prose):
{{
  "recipe": {{
    "ingredients": [
      {{"name": "Specific product name from available products", "type": "part|tool|product"}},
      {{"name": "Another specific product name", "type": "part|tool|product"}},
      {{"name": "Tool: Specific tool name if applicable", "type": "tool"}}
    ],
    "steps": [
      "Step 1: Detailed instruction using ingredients. Attach the Specific product name and tighten with Tool name.",
      "Step 2: Next step. Use Another specific product name according to the requirements.",
      "Step 3: Final assembly or verification step using the ingredients."
    ]
  }},
  "primary_products": [
    {{
      "category": "category_key",
      "product_index": 0,
      "reasoning": "1-2 sentence explanation why this product fits the job."
    }}
  ],
  "tools": [
    {{
      "category": "category_key",
      "product_index": 0,
      "reasoning": "1-2 sentence explanation why this tool is needed."
    }}
  ],
  "optional_extras": [
    {{
      "category": "category_key",
      "product_index": 0,
      "reasoning": "1-2 sentence explanation of why this might be useful but isn't required."
    }}
  ],
  "diagnosis": "One sentence summary of the complete solution."
}}

RULES FOR RECIPE FORMAT:
- EVERY ingredient must have both "name" and "type" fields
- Ingredient types: "part" (bike component), "tool" (tool needed), "product" (purchasable item)
- EVERY ingredient must appear in at least one step (check this carefully!)
- EVERY reference in steps must be to an ingredient name in the list
- Steps should be detailed, actionable, and reference ingredients naturally
- Use ONLY products from the AVAILABLE PRODUCTS list above
- product_index refers to the "index" field in each product
- primary_products: Products explicitly needed for the job (from ingredients)
- tools: Tool products needed to complete the work
- optional_extras: Maximum 3 items NOT in ingredients but potentially useful
- Each reasoning should be specific to this user's situation (not generic)
- Verify product specifications match the clarified values

RECIPE VALIDATION:
Before submitting, check:
  ✓ Every ingredient in the list is mentioned at least once in the steps
  ✓ Every product reference in steps is in the ingredients list
  ✓ Each step is clear and actionable
  ✓ The recipe flows logically from start to finish
"""
