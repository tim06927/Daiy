"""Job identification for dynamic product recommendations.

This module handles the first step of the generalized flow: analyzing user input
to determine which product categories are relevant and what fit dimensions
need to be clarified.
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Optional, Tuple

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
    """Result of job identification step.
    
    Distinguishes between:
    - primary_categories: What the user explicitly requested
    - optional_categories: Complementary products the LLM recommends for this specific job
    - required_tools: Tools needed to complete the job
    """
    
    def __init__(
        self,
        primary_categories: List[str],
        optional_categories: List[str],
        required_tools: List[str],
        inferred_values: Dict[str, Any],
        missing_dimensions: List[str],
        confidence: float,
        reasoning: str,
        optional_reasons: Optional[Dict[str, str]] = None,
        tool_reasons: Optional[Dict[str, str]] = None,
    ):
        """Initialize job identification result.
        
        Args:
            primary_categories: Categories the user explicitly asked for (ordered by priority).
            optional_categories: Complementary categories the LLM recommends for this job.
            required_tools: Tool categories needed to complete the job.
            inferred_values: Dict of fit dimension values inferred from input.
            missing_dimensions: List of fit dimensions that need clarification.
            confidence: Confidence score (0-1) for the identification.
            reasoning: Brief explanation of why these categories were identified.
            optional_reasons: Dict mapping optional category to reason why it's suggested.
            tool_reasons: Dict mapping tool category to reason why it's needed.
        """
        self.primary_categories = primary_categories
        self.optional_categories = optional_categories
        self.required_tools = required_tools
        self.inferred_values = inferred_values
        self.missing_dimensions = missing_dimensions
        self.confidence = confidence
        self.reasoning = reasoning
        self.optional_reasons = optional_reasons or {}
        self.tool_reasons = tool_reasons or {}
    
    @property
    def categories(self) -> List[str]:
        """All categories (for backwards compatibility)."""
        return self.primary_categories + self.optional_categories + self.required_tools
    
    @categories.setter
    def categories(self, value: List[str]) -> None:
        """Set categories (for backwards compatibility during validation)."""
        # When setting categories, assume they are all primary for backwards compat
        self.primary_categories = value
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "primary_categories": self.primary_categories,
            "optional_categories": self.optional_categories,
            "required_tools": self.required_tools,
            "optional_reasons": self.optional_reasons,
            "tool_reasons": self.tool_reasons,
            "inferred_values": self.inferred_values,
            "missing_dimensions": self.missing_dimensions,
            "confidence": self.confidence,
            "reasoning": self.reasoning,
            # Backwards compatibility
            "categories": self.categories,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "JobIdentification":
        """Create from dictionary."""
        # Handle both new and old format
        if "primary_categories" in data:
            return cls(
                primary_categories=data.get("primary_categories", []),
                optional_categories=data.get("optional_categories", []),
                required_tools=data.get("required_tools", []),
                inferred_values=data.get("inferred_values", {}),
                missing_dimensions=data.get("missing_dimensions", []),
                confidence=data.get("confidence", 0.0),
                reasoning=data.get("reasoning", ""),
                optional_reasons=data.get("optional_reasons", {}),
                tool_reasons=data.get("tool_reasons", {}),
            )
        else:
            # Old format - treat all as primary
            return cls(
                primary_categories=data.get("categories", []),
                optional_categories=[],
                required_tools=[],
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
    
    return f"""You are a bike shop assistant helping to identify what products a customer needs for their specific job.

{category_descriptions}

{dimension_descriptions}

USER REQUEST:
\"\"\"{problem_text}\"\"\"
{image_instruction}
YOUR TASK:
Analyze the user's request and identify:
1. PRIMARY PRODUCTS: What the user explicitly asked for (ordered by importance to the user)
2. OPTIONAL PRODUCTS: Other products you'd recommend specifically for THIS job (not generic "often bought together")
3. REQUIRED TOOLS: Tools necessary to complete this specific job
4. Infer any fit dimension values from the text/image
5. List which fit dimensions still need clarification

Respond with pure JSON ONLY (no prose), using this exact structure:
{{
  "primary_categories": ["drivetrain_chains"],  // What user explicitly requested, ordered by priority
  "optional_categories": ["drivetrain_cassettes"],  // Products that make sense for THIS specific job
  "optional_reasons": {{"drivetrain_cassettes": "Old chain may have worn the cassette - inspect and consider replacing"}},
  "required_tools": ["drivetrain_tools"],  // Tool categories needed for installation
  "tool_reasons": {{"drivetrain_tools": "Chain breaker or quick-link pliers needed for chain replacement"}},
  "inferred_values": {{
    "gearing": 11,  // Values you can determine, or null if unknown
    "use_case": "road"  // Set to null if not determinable
  }},
  "missing_dimensions": ["freehub_compatibility"],  // Dimensions that need user input
  "confidence": 0.85,  // 0-1 score of confidence in job identification
  "reasoning": "User needs chain replacement for their road bike drivetrain"
}}

RULES:
- PRIMARY: Only include what the user explicitly asked for. Order by user's stated priority.
- OPTIONAL: Only include if there's a specific reason for THIS job (e.g., worn chain damages cassette).
  Do NOT include generic "often bought together" items without job-specific reasoning.
- TOOLS: Include tool categories that are genuinely needed to complete the job.
- For inferred_values: only include dimensions relevant to the identified categories
- For missing_dimensions: list dimensions that ARE relevant but COULDN'T be determined
- Keep reasoning brief (1-2 sentences)
- Set confidence lower if the request is ambiguous
"""


def _ensure_required_dimensions(job: "JobIdentification") -> None:
    """Ensure all required fit dimensions for identified categories are tracked.
    
    If a required dimension is not in inferred_values AND not in missing_dimensions,
    add it to missing_dimensions. This ensures the clarification flow will ask
    for necessary information.
    
    Args:
        job: JobIdentification result to modify in place.
    """
    # Collect all required fit dimensions from identified categories
    all_categories = job.primary_categories + job.optional_categories
    required_dims = set()
    
    for cat in all_categories:
        cat_config = PRODUCT_CATEGORIES.get(cat, {})
        for dim in cat_config.get("required_fit", []):
            required_dims.add(dim)
    
    # Check which required dimensions are missing
    inferred = job.inferred_values or {}
    missing = set(job.missing_dimensions or [])
    
    for dim in required_dims:
        # If not inferred (or inferred as None) and not already marked as missing
        if inferred.get(dim) is None and dim not in missing:
            missing.add(dim)
            logger.debug(f"Added required dimension '{dim}' to missing_dimensions")
    
    # Update job's missing_dimensions
    job.missing_dimensions = list(missing)


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
                    
                    # Validate categories against known list
                    valid_categories = get_all_category_names()
                    
                    # Parse new format with primary/optional/tools
                    primary_categories = [
                        c for c in parsed.get("primary_categories", [])
                        if c in valid_categories
                    ]
                    optional_categories = [
                        c for c in parsed.get("optional_categories", [])
                        if c in valid_categories
                    ]
                    required_tools = [
                        c for c in parsed.get("required_tools", [])
                        if c in valid_categories
                    ]
                    
                    # Backwards compatibility: if old format used, treat as primary
                    if not primary_categories and "categories" in parsed:
                        primary_categories = [
                            c for c in parsed.get("categories", [])
                            if c in valid_categories
                        ]
                    
                    # If no categories at all, try to infer from context
                    if not primary_categories:
                        logger.warning("No valid primary categories identified, using defaults")
                        # Check for common keywords and map to categories
                        text_lower = problem_text.lower()
                        if any(w in text_lower for w in ["chain", "cassette", "drivetrain", "gearing"]):
                            primary_categories = ["drivetrain_chains"]
                            optional_categories = ["drivetrain_cassettes"]
                            required_tools = ["drivetrain_tools"]
                        elif "glove" in text_lower:
                            primary_categories = ["mtb_gloves"]
                        elif "tool" in text_lower:
                            primary_categories = ["drivetrain_tools"]
                        else:
                            # Default fallback
                            primary_categories = ["drivetrain_chains"]
                    
                    result = JobIdentification(
                        primary_categories=primary_categories,
                        optional_categories=optional_categories,
                        required_tools=required_tools,
                        optional_reasons=parsed.get("optional_reasons", {}),
                        tool_reasons=parsed.get("tool_reasons", {}),
                        inferred_values=parsed.get("inferred_values", {}),
                        missing_dimensions=parsed.get("missing_dimensions", []),
                        confidence=float(parsed.get("confidence", 0.5)),
                        reasoning=parsed.get("reasoning", ""),
                    )
                    
                    # Ensure all required fit dimensions are tracked
                    # If LLM didn't infer a required dimension, add it to missing
                    _ensure_required_dimensions(result)
                    
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
        primary_categories=["drivetrain_chains"],
        optional_categories=["drivetrain_cassettes"],
        required_tools=["drivetrain_tools"],
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
