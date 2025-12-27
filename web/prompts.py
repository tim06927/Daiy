"""Dynamic prompt generation for LLM recommendations.

This module provides category-agnostic prompt building, replacing
the hardcoded make_prompt() function.
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
    "build_grounding_context_dynamic",
]

logger = logging.getLogger(__name__)


def _format_product_list(
    category_key: str,
    products: List[Dict[str, Any]],
) -> str:
    """Format a product list for the prompt.
    
    Args:
        category_key: Category key for labeling.
        products: List of product dicts.
        
    Returns:
        Formatted string for prompt inclusion.
    """
    config = get_category_config(category_key)
    label = config["display_name"] if config else category_key.replace("_", " ").title()
    
    if not products:
        return f"{label}: [] (no matching products found)"
    
    lines = [f"{label} (0-based index, use only these):"]
    for idx, p in enumerate(products):
        lines.append(
            f"  {idx}: {p.get('name')} | "
            f"brand: {p.get('brand')} | "
            f"speed: {p.get('speed')} | "
            f"application: {p.get('application')} | "
            f"price: {p.get('price')} | "
            f"url: {p.get('url')}"
        )
    return "\n".join(lines)


def build_grounding_context_dynamic(
    problem_text: str,
    categories: List[str],
    fit_values: Dict[str, Any],
    candidates: Dict[str, List[Dict[str, Any]]],
    image_base64: Optional[str] = None,
) -> Dict[str, Any]:
    """Build grounding context for dynamic recommendation.
    
    Args:
        problem_text: User's problem description.
        categories: Identified categories.
        fit_values: Known fit dimension values.
        candidates: Dict of candidates per category.
        image_base64: Optional base64 image.
        
    Returns:
        Context dict for prompt generation.
    """
    # Build category descriptions
    category_descriptions = []
    for cat in categories:
        config = get_category_config(cat)
        if config:
            category_descriptions.append(f"{config['display_name']}: {config['description']}")
    
    return {
        "project": f"Product recommendation for: {', '.join(categories)}",
        "user_request": problem_text,
        "identified_categories": categories,
        "category_descriptions": category_descriptions,
        "fit_values": fit_values,
        "candidates": candidates,
        "image_base64": image_base64,
    }


def make_recommendation_prompt(
    context: Dict[str, Any],
    image_attached: bool = False,
) -> str:
    """Generate a category-agnostic recommendation prompt.
    
    Args:
        context: Grounding context from build_grounding_context_dynamic.
        image_attached: Whether user image is attached.
        
    Returns:
        Prompt string for LLM.
    """
    categories = context.get("identified_categories", [])
    candidates = context.get("candidates", {})
    fit_values = context.get("fit_values", {})
    user_text = context.get("user_request", "")
    
    # Build candidate blocks
    candidate_blocks = []
    for cat in categories:
        products = candidates.get(cat, [])
        candidate_blocks.append(_format_product_list(cat, products))
    candidates_text = "\n\n".join(candidate_blocks)
    
    # Build fit info
    fit_info_lines = []
    for key, value in fit_values.items():
        if value is not None:
            fit_info_lines.append(f"  - {key}: {value}")
    fit_info = "\n".join(fit_info_lines) if fit_info_lines else "  (no specific fit requirements)"
    
    # Build category list for response format
    category_keys = [cat for cat in categories if candidates.get(cat)]
    
    # Build product_ranking example based on actual categories
    ranking_example_parts = []
    for cat in category_keys:
        ranking_example_parts.append(f'''    "{cat}": {{
      "best_index": 0,
      "alternatives": [1, 2],
      "why_fits": {{"0": "Explanation for product 0", "1": "Explanation for product 1"}}
    }}''')
    ranking_example = ",\n".join(ranking_example_parts)
    
    image_note = (
        "\nUser uploaded a photo (attached as image input). "
        "Consider visual cues if relevant to the recommendations.\n"
        if image_attached
        else ""
    )
    
    # Build the prompt
    return f"""You are an experienced bike shop assistant. Recommend ONE best product from EACH category from the provided candidates only.

User request:
\"\"\"{user_text}\"\"\"

Detected fit requirements:
{fit_info}
{image_note}
Candidate products (do NOT invent anything else):
{candidates_text}

RESPONSE FORMAT (return JSON ONLY, no prose):
{{
  "diagnosis": "Short 1-sentence diagnosis of what the user needs",
  "sections": {{
    "why_it_fits": ["bullet 1 explaining overall fit", "bullet 2", "bullet 3"],
    "suggested_workflow": ["step 1", "step 2", "step 3"],
    "checklist": ["tool/part 1", "tool/part 2", "consumable 1"]
  }},
  "product_ranking": {{
{ranking_example}
  }}
}}

RULES:
- Use 0-based indices that exist in the candidate lists above.
- Choose exactly one best_index per category; alternatives are optional and must be unique.
- For EACH recommended product (best + alternatives), include a why_fits entry explaining why it matches the user's needs.
- Keep why_fits explanations short (8-15 words), specific to the user's situation.
- Keep bullets concise (max ~15 words each), 3-5 bullets for why_it_fits.
- Provide 3-6 workflow steps, actionable and ordered.
- Provide a checklist of 5-10 concise items (tools/parts/consumables relevant to the recommended products).
- Do not include any text outside the JSON.
- Only recommend products from categories where candidates are available.
"""


def make_clarification_prompt_dynamic(
    problem_text: str,
    categories: List[str],
    missing_dimensions: List[str],
    image_attached: bool = False,
) -> str:
    """Generate a prompt for dynamic clarification.
    
    Args:
        problem_text: User's problem description.
        categories: Identified categories.
        missing_dimensions: Dimensions that need clarification.
        image_attached: Whether user image is attached.
        
    Returns:
        Prompt string for clarification LLM call.
    """
    # Import SHARED_FIT_DIMENSIONS (handle both direct and package import)
    if __package__ is None or __package__ == "":
        from categories import SHARED_FIT_DIMENSIONS
    else:
        from .categories import SHARED_FIT_DIMENSIONS
    
    # Build dimension descriptions
    dim_descriptions = []
    for dim in missing_dimensions:
        config = SHARED_FIT_DIMENSIONS.get(dim)
        if config:
            dim_descriptions.append(f"  - {dim}: {config['display_name']} ({config['hint']})")
    dims_text = "\n".join(dim_descriptions)
    
    # Build options format
    options_format = {}
    for dim in missing_dimensions:
        config = SHARED_FIT_DIMENSIONS.get(dim)
        if config:
            options_format[f"{dim}_options"] = config.get("options", [])
    options_example = json.dumps(options_format, indent=2)
    
    image_instruction = ""
    if image_attached:
        image_instruction = (
            "\n\nIMPORTANT - IMAGE ANALYSIS:\n"
            "The user has uploaded a PHOTO. Carefully analyze the image to:\n"
            "- Extract relevant fit information visible in the image\n"
            "- Count components (e.g., cassette cogs for speed)\n"
            "- Identify bike type, component brands, or sizing\n"
            "Use this visual information to infer values before asking for clarification.\n"
        )
    
    return f"""You are assisting a bike product recommender. The user wrote:
\"\"\"{problem_text}\"\"\"

We need to know these fit dimensions for the identified categories ({', '.join(categories)}):
{dims_text}
{image_instruction}
YOUR TASK: Analyze the user's text (and image if provided) and either:
1. INFER the missing values if clearly stated, strongly implied, or visible in the image, OR
2. PROPOSE option lists if the information is truly ambiguous or absent.

Respond with pure JSON ONLY (no prose), using this structure:
{{
  "inferred_values": {{
    // For each dimension you CAN determine, include it here
    // e.g., "gearing": 11, "use_case": "road"
  }},
  "options": {options_example}
}}

RULES:
- For each dimension: either put it in inferred_values OR provide options, not both
- If you can determine a value confidently, use inferred_values
- If you cannot determine, provide relevant options from the standard list
- Keep option lists to max 5 items with short labels
"""
