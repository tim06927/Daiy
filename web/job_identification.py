"""Job identification for dynamic product recommendations.

This module handles the first step of the generalized flow: analyzing user input
to determine which product categories are relevant and what fit dimensions
need to be clarified.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Handle imports for both direct execution and package import
if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).parent))
    from categories import (
        PRODUCT_CATEGORIES,
        SHARED_FIT_DIMENSIONS,
        get_categories_for_prompt,
        get_all_category_names,
    )
    from config import LLM_MODEL
    from logging_utils import log_interaction
else:
    from .categories import (
        PRODUCT_CATEGORIES,
        SHARED_FIT_DIMENSIONS,
        get_categories_for_prompt,
        get_all_category_names,
    )
    from .config import LLM_MODEL
    from .logging_utils import log_interaction

__all__ = [
    "identify_job",
    "JobIdentification",
]

logger = logging.getLogger(__name__)


def _get_openai_client():
    """Get OpenAI client (lazy initialization)."""
    from openai import OpenAI
    return OpenAI()


class JobIdentification:
    """Result of job identification step."""
    
    def __init__(
        self,
        categories: List[str],
        inferred_values: Dict[str, Any],
        missing_dimensions: List[str],
        confidence: float,
        reasoning: str,
    ):
        """Initialize job identification result.
        
        Args:
            categories: List of identified product category keys.
            inferred_values: Dict of fit dimension values inferred from input.
            missing_dimensions: List of fit dimensions that need clarification.
            confidence: Confidence score (0-1) for the identification.
            reasoning: Brief explanation of why these categories were identified.
        """
        self.categories = categories
        self.inferred_values = inferred_values
        self.missing_dimensions = missing_dimensions
        self.confidence = confidence
        self.reasoning = reasoning
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "categories": self.categories,
            "inferred_values": self.inferred_values,
            "missing_dimensions": self.missing_dimensions,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobIdentification":
        """Create from dictionary."""
        return cls(
            categories=data.get("categories", []),
            inferred_values=data.get("inferred_values", {}),
            missing_dimensions=data.get("missing_dimensions", []),
            confidence=data.get("confidence", 0.0),
            reasoning=data.get("reasoning", ""),
        )


def _build_job_identification_prompt(
    problem_text: str,
    image_attached: bool = False,
) -> str:
    """Build the prompt for job identification.
    
    Args:
        problem_text: User's description of their needs.
        image_attached: Whether a user image is attached.
        
    Returns:
        Formatted prompt string.
    """
    category_descriptions = get_categories_for_prompt()
    
    # Build dimension descriptions
    dim_lines = ["Fit dimensions that may need clarification:"]
    for dim, config in SHARED_FIT_DIMENSIONS.items():
        dim_lines.append(f"  - {dim}: {config['display_name']} - {config['hint']}")
    dimension_descriptions = "\n".join(dim_lines)
    
    # Image analysis instructions
    image_instruction = ""
    if image_attached:
        image_instruction = (
            "\n\nIMPORTANT - IMAGE ANALYSIS:\n"
            "The user has uploaded a PHOTO. Carefully analyze the image to:\n"
            "- Identify what components/products are shown\n"
            "- Determine relevant fit dimensions from visual cues\n"
            "  (e.g., count cassette cogs for gearing, identify bike type)\n"
            "- Look for brand logos or component markings\n"
            "Use visual information to infer categories and fit values.\n"
        )
    
    return f"""You are a bike shop assistant helping to identify what products a customer needs.

{category_descriptions}

{dimension_descriptions}

USER REQUEST:
\"\"\"{problem_text}\"\"\"
{image_instruction}
YOUR TASK:
1. Identify which product categories are relevant to the user's request
2. Infer any fit dimension values you can determine from the text (or image if provided)
3. List which fit dimensions still need clarification

Respond with pure JSON ONLY (no prose), using this exact structure:
{{
  "categories": ["cassettes", "chains"],  // List of relevant category keys from above
  "inferred_values": {{
    "gearing": 11,  // Values you can determine, or null if unknown
    "use_case": "road"  // Set to null if not determinable
  }},
  "missing_dimensions": ["freehub_compatibility"],  // Dimensions that need user input
  "confidence": 0.85,  // 0-1 score of confidence in category identification
  "reasoning": "User mentions worn chain and cassette, appears to be road bike from image"
}}

RULES:
- Only include categories from the available list above
- Include a category ONLY if the user explicitly or implicitly needs that type of product
- For inferred_values: only include dimensions relevant to the identified categories
- For missing_dimensions: list dimensions that ARE relevant but COULDN'T be determined
- If user mentions tools/maintenance without specific products, include relevant tool categories
- Keep reasoning brief (1-2 sentences)
- Set confidence lower if the request is ambiguous
"""


def identify_job(
    problem_text: str,
    image_base64: Optional[str] = None,
    image_meta: Optional[Dict[str, Any]] = None,
) -> JobIdentification:
    """Identify job from user input using LLM.
    
    This is the first step in the generalized recommendation flow. It analyzes
    the user's request to determine:
    - Which product categories are relevant
    - What fit dimension values can be inferred
    - What still needs clarification
    
    Args:
        problem_text: User's description of their needs.
        image_base64: Optional base64-encoded image.
        image_meta: Optional metadata about the image.
        
    Returns:
        JobIdentification result with categories and inferred values.
    """
    image_attached = bool(image_base64)
    prompt = _build_job_identification_prompt(problem_text, image_attached)
    
    # Log the call
    log_interaction(
        "llm_call_job_identification",
        {
            "model": LLM_MODEL,
            "prompt": prompt,
            "user_text": problem_text,
            "image_attached": image_attached,
            "image_meta": image_meta or {},
        },
    )
    
    # Build input payload
    input_payload = [{"role": "user", "content": [{"type": "input_text", "text": prompt}]}]
    if image_base64:
        input_payload.append(
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_image",
                        "image_url": f"data:image/png;base64,{image_base64}",
                    }
                ],
            }
        )
    
    try:
        client = _get_openai_client()
        resp = client.responses.create(
            model=LLM_MODEL,
            input=input_payload,
        )
        
        for item in resp.output:
            if hasattr(item, "content") and item.content is not None:
                raw = item.content[0].text  # type: ignore[union-attr]
                
                log_interaction(
                    "llm_response_job_identification",
                    {
                        "model": LLM_MODEL,
                        "raw_response": raw,
                    },
                )
                
                try:
                    parsed = json.loads(raw)
                    
                    # Validate categories
                    valid_categories = get_all_category_names()
                    categories = [
                        c for c in parsed.get("categories", [])
                        if c in valid_categories
                    ]
                    
                    # If no valid categories, try to infer from context
                    if not categories:
                        logger.warning("No valid categories identified, using defaults")
                        # Check for common keywords and map to categories
                        text_lower = problem_text.lower()
                        if any(w in text_lower for w in ["chain", "cassette", "drivetrain", "gearing"]):
                            categories = ["chains", "cassettes"]
                        elif "glove" in text_lower:
                            categories = ["mtb_gloves"]
                        elif "tool" in text_lower:
                            categories = ["drivetrain_tools"]
                        else:
                            # Default fallback
                            categories = ["chains", "cassettes", "drivetrain_tools"]
                    
                    result = JobIdentification(
                        categories=categories,
                        inferred_values=parsed.get("inferred_values", {}),
                        missing_dimensions=parsed.get("missing_dimensions", []),
                        confidence=float(parsed.get("confidence", 0.5)),
                        reasoning=parsed.get("reasoning", ""),
                    )
                    
                    log_interaction("job_identification_result", result.to_dict())
                    return result
                    
                except json.JSONDecodeError as e:
                    log_interaction(
                        "llm_parse_error_job_identification",
                        {"error": str(e), "raw": raw},
                    )
                    
    except Exception as e:
        log_interaction(
            "llm_error_job_identification",
            {"error": str(e)},
        )
        logger.exception("Error during job identification")
    
    # Fallback: return drivetrain categories with unknown values
    logger.warning("Job identification failed, using fallback")
    return JobIdentification(
        categories=["chains", "cassettes", "drivetrain_tools"],
        inferred_values={},
        missing_dimensions=["gearing", "use_case"],
        confidence=0.0,
        reasoning="Fallback: could not identify specific job from input",
    )


def merge_inferred_with_user_selections(
    job: JobIdentification,
    user_selections: Dict[str, Any],
) -> Dict[str, Any]:
    """Merge LLM-inferred values with explicit user selections.
    
    User selections take precedence over inferred values.
    
    Args:
        job: Job identification result.
        user_selections: Dict of user-provided values.
        
    Returns:
        Merged dict of all known fit dimension values.
    """
    result = dict(job.inferred_values)
    for key, value in user_selections.items():
        if value is not None:
            result[key] = value
    return result
